#!/usr/bin/env python3
"""
Compute burst-aware Azure OpenAI PTU sizing metrics using Azure Monitor totals for
ProcessedPromptTokens and ProcessedCompletionTokens. Mirrors the reference KQL query
used for PTU capacity planning.
"""
import argparse
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

PROMPT_METRIC_NAME = "ProcessedPromptTokens"
COMPLETION_METRIC_CANDIDATES = [
    "ProcessedCompletionTokens",
    "GeneratedTokens",
    "OutputTokens",
]
PTU_TOKEN_CAPACITY = 37000.0


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_datetime_iso(dt: datetime) -> str:
    return ensure_utc(dt).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_timespan(start: datetime, end: datetime) -> str:
    return f"{format_datetime_iso(start)}/{format_datetime_iso(end)}"


def timedelta_to_iso8601(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        raise ValueError("Interval must be positive")
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = (total_seconds // 3600) % 24
    days = total_seconds // 86400

    parts = ["P"]
    if days:
        parts.append(f"{days}D")
    if hours or minutes or seconds:
        parts.append("T")
        if hours:
            parts.append(f"{hours}H")
        if minutes:
            parts.append(f"{minutes}M")
        if seconds:
            parts.append(f"{seconds}S")
    if len(parts) == 1:
        parts.extend(["T", "0S"])
    return "".join(parts)


def extract_timestamp(data_point) -> Optional[datetime]:
    raw = getattr(data_point, "time_stamp", getattr(data_point, "timestamp", None))
    if isinstance(raw, datetime):
        return ensure_utc(raw)
    return raw


def extract_total(data_point) -> Optional[float]:
    total = getattr(data_point, "total", None)
    if total is None:
        return None
    try:
        return float(total)
    except (TypeError, ValueError):
        return None


def percentile(values: Iterable[float], pct: float) -> float:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return float("nan")
    try:
        return float(np.percentile(arr, pct, method="linear"))
    except TypeError:
        return float(np.percentile(arr, pct))


def query_token_totals(
    client: MonitorManagementClient,
    resource_id: str,
    timespan: str,
    granularity: timedelta,
    metric_filter: Optional[str],
    completion_metric: Optional[str],
    logger: logging.Logger,
) -> Tuple[Dict[datetime, float], List[str]]:
    logger.debug("Fetching token totals (filter=%s)", metric_filter)

    def fetch_metric(metric_name: str) -> Dict[datetime, float]:
        try:
            metrics_response = client.metrics.list(
                resource_id,
                timespan=timespan,
                interval=timedelta_to_iso8601(granularity),
                metricnames=metric_name,
                aggregation="Total",
                filter=metric_filter,
            )
        except HttpResponseError as ex:
            msg = (ex.message if hasattr(ex, "message") else str(ex) or "").lower()
            if "failed to find metric configuration" in msg or "metricnotfound" in msg:
                logger.info("Metric '%s' unavailable for this resource", metric_name)
                return {}
            raise

        totals: Dict[datetime, float] = {}
        for metric in getattr(metrics_response, "value", []) or []:
            for ts in getattr(metric, "timeseries", []) or []:
                for point in getattr(ts, "data", []) or []:
                    timestamp = extract_timestamp(point)
                    value = extract_total(point)
                    if timestamp is None or value is None:
                        continue
                    totals[timestamp] = totals.get(timestamp, 0.0) + value
        return totals

    tokens: Dict[datetime, float] = {}
    used_metrics: List[str] = []

    prompt_totals = fetch_metric(PROMPT_METRIC_NAME)
    if prompt_totals:
        used_metrics.append(PROMPT_METRIC_NAME)
        for ts, value in prompt_totals.items():
            tokens[ts] = tokens.get(ts, 0.0) + value
    else:
        logger.warning("Metric '%s' returned no data; proceeding with completion metrics only", PROMPT_METRIC_NAME)

    completion_candidates: Iterable[str]
    if completion_metric and completion_metric.lower() != "auto":
        completion_candidates = [completion_metric]
    else:
        completion_candidates = COMPLETION_METRIC_CANDIDATES

    completion_used = None
    for metric_name in completion_candidates:
        if metric_name == PROMPT_METRIC_NAME:
            continue
        totals = fetch_metric(metric_name)
        if totals:
            completion_used = metric_name
            used_metrics.append(metric_name)
            for ts, value in totals.items():
                tokens[ts] = tokens.get(ts, 0.0) + value
            break
    if completion_metric and completion_metric.lower() != "auto" and completion_used is None:
        logger.warning("Requested completion metric '%s' was unavailable.", completion_metric)

    return tokens, used_metrics


def compute_ptu_stats(tokens_by_timestamp: Dict[datetime, float], burst_percentile: float) -> Tuple[float, float, float]:
    if not tokens_by_timestamp:
        return (0.0, 0.0, 0.0)
    values = list(tokens_by_timestamp.values())
    avg_tpm = float(np.mean(values))
    pxx_tpm = percentile(values, burst_percentile)
    max_tpm = max(values)
    return avg_tpm, pxx_tpm, max_tpm


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate PTU sizing recommendations from Azure Monitor metrics.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days to query (default: 7)")
    parser.add_argument("--granularity-mins", type=int, default=1, help="Time grain in minutes for burst detection (default: 1)")
    parser.add_argument("--percentile", type=float, default=99.0, help="Burst percentile to calculate (default: 99)")
    parser.add_argument("--dimension-filter", default=None, help="Optional Azure Monitor filter expression (e.g., ModelDeploymentName eq 'foo')")
    parser.add_argument(
        "--model-deployment",
        default=None,
        help="Limit results to a specific ModelDeploymentName value.",
    )
    parser.add_argument(
        "--completion-metric",
        default="auto",
        help=(
            "Specify the completion token metric to use (ProcessedCompletionTokens, GeneratedTokens, OutputTokens). "
            "Use 'auto' to try them in order."
        ),
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.days <= 0:
        raise ValueError("--days must be positive")
    if args.granularity_mins <= 0:
        raise ValueError("--granularity-mins must be positive")
    if not (0 < args.percentile <= 100):
        raise ValueError("--percentile must be within 0-100")

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    logger = logging.getLogger("ptu_sizing")

    load_dotenv()
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP_NAME")
    resource_name = os.getenv("AZURE_AOAI_RESOURCE_NAME")
    if not all([subscription_id, resource_group, resource_name]):
        raise RuntimeError("AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP_NAME, AZURE_AOAI_RESOURCE_NAME must be set")

    resource_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/"
        f"providers/Microsoft.CognitiveServices/accounts/{resource_name}"
    )

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=args.days)
    timespan = build_timespan(start_time, end_time)
    granularity = timedelta(minutes=args.granularity_mins)

    dimension_filter = args.dimension_filter
    if args.model_deployment:
        deployment_value = args.model_deployment.replace("'", "''")
        deployment_filter = f"ModelDeploymentName eq '{deployment_value}'"
        if dimension_filter:
            dimension_filter = f"({dimension_filter}) and {deployment_filter}"
        else:
            dimension_filter = deployment_filter

    logger.info(
        "Querying token metrics with granularity %sm over %s (completion metric=%s, filter=%s)",
        args.granularity_mins,
        timespan,
        args.completion_metric,
        dimension_filter or "<none>",
    )

    credential = DefaultAzureCredential()
    client = MonitorManagementClient(credential, subscription_id)

    tokens, used_metrics = query_token_totals(
        client,
        resource_id,
        timespan,
        granularity,
        dimension_filter,
        args.completion_metric,
        logger,
    )
    avg_tpm, pxx_tpm, max_tpm = compute_ptu_stats(tokens, args.percentile)

    if not tokens:
        print("No token data returned for the specified window.")
        return

    avg_ptu = math.ceil(avg_tpm / PTU_TOKEN_CAPACITY)
    pxx_ptu = math.ceil(pxx_tpm / PTU_TOKEN_CAPACITY)
    max_ptu = math.ceil(max_tpm / PTU_TOKEN_CAPACITY)
    recommended_ptu = max(avg_ptu, pxx_ptu)

    print("Burst-Aware Azure OpenAI PTU Sizing Analysis")
    print(f"Lookback: {args.days}d | Granularity: {args.granularity_mins}m | Percentile: P{args.percentile}")
    if used_metrics:
        print(f"MetricsUsed: {', '.join(used_metrics)}")
    print("")
    print(f"AvgTPM: {avg_tpm:,.2f}")
    print(f"P{args.percentile:.0f}TPM: {pxx_tpm:,.2f}")
    print(f"MaxTPM: {max_tpm:,.2f}")
    print("")
    print(f"AvgPTU: {avg_ptu}")
    print(f"P{args.percentile:.0f}PTU: {pxx_ptu}")
    print(f"MaxPTU: {max_ptu}")
    print("")
    print(f"RecommendedPTU: {recommended_ptu}")


if __name__ == "__main__":
    main()
