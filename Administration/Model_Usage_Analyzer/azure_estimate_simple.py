
#!/usr/bin/env python3
"""
Simple estimator that reports overall and per-deployment completion (output) tokens per request
using Azure Monitor metrics with a dimension split (e.g., ModelDeploymentName).
"""
import os
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import numpy as np
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.monitor.query import MetricsQueryClient
import logging


def key_from_metadata(ts, preferred_dim: str) -> str:
    mvs = getattr(ts, 'metadata_values', None) or []
    print(f"Metadata values: {mvs}")
    return mvs.get(preferred_dim, '') if mvs else 'all'


def main():
    parser = argparse.ArgumentParser(description="Estimate expected completion tokens per model request.")
    parser.add_argument('--debug', action='store_true', help='Enable debug logs')
    parser.add_argument('--days', type=int, default=1, help='Timespan in days to query (default: 30)')
    parser.add_argument('--granularity-mins', type=int, default=60, help='Granularity in minutes (default: 5)')
    parser.add_argument('--dimension-name', default='ModelDeploymentName', help='Dimension to split by (default: ModelDeploymentName)')
    parser.add_argument('--req-metric', default='AzureOpenAIRequests', help='Metric name for request counts (default: AzureOpenAIRequests)')
    parser.add_argument('--tok-metric', default='GeneratedTokens', help='Metric name for output tokens (default: GeneratedTokens)')
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    load_dotenv()
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    rg = os.getenv('AZURE_RESOURCE_GROUP_NAME')
    resource_name = os.getenv('AZURE_AOAI_RESOURCE_NAME')
    if not all([subscription_id, rg, resource_name]):
        raise ValueError("AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP_NAME, AZURE_AOAI_RESOURCE_NAME must be set")

    resource_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{rg}"
        f"/providers/Microsoft.CognitiveServices/accounts/{resource_name}"
    )

    credential = DefaultAzureCredential()
    client = MetricsQueryClient(credential)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    logger.info(f"Querying metrics from {start.date()} to {end.date()} split by {args.dimension_name} at {args.granularity_mins}-minute granularity")

    metrics = [args.req_metric, args.tok_metric]
    filt = f"{args.dimension_name} eq '*'"
    try:
        resp = client.query_resource(
            resource_uri=resource_id,
            metric_names=metrics,
            timespan=(start, end),
            granularity=timedelta(minutes=args.granularity_mins),
            aggregations=['Total'],
            filter=filt,
        )
    except Exception as ex:
        logger.error(f"Failed to query metrics: {ex}")
        return

    per_metric_by_dep = {}
    series_len = None

    #write metrics to file: 
    for metric in resp.metrics:
        print(metric.name)
        for time_series_element in metric.timeseries:
            print(time_series_element.metadata_values)
            for metric_value in time_series_element.data:
                print(metric_value.__dict__)

    for m in resp.metrics:
        by_dep = {}
        for ts in m.timeseries:
            vals = np.array([float(getattr(pt, 'total', 0) or 0) for pt in ts.data], dtype=float)
            key = key_from_metadata(ts,  str.lower(args.dimension_name))
            print(key)
            if key not in by_dep:
                by_dep[key] = vals
            else:
                n = min(len(by_dep[key]), len(vals))
                if n:
                    by_dep[key] = by_dep[key][:n] + vals[:n]
        for arr in by_dep.values():
            series_len = len(arr) if series_len is None else min(series_len, len(arr))
        per_metric_by_dep[m.name] = by_dep

    if not series_len:
        logger.warning("No metric data points returned. Cannot estimate.")
        return

    keys = set()
    for d in per_metric_by_dep.values():
        keys.update(d.keys())
    if not keys:
        keys = {'all'}

    per_dep = {}
    for key in keys:
        reqs = per_metric_by_dep.get(args.req_metric, {}).get(key, np.zeros(series_len))[:series_len]
        outs = per_metric_by_dep.get(args.tok_metric, {}).get(key, np.zeros(series_len))[:series_len]
        n = min(len(reqs), len(outs), series_len)
        reqs = np.array(reqs[:n], dtype=float)
        outs = np.array(outs[:n], dtype=float)
        per_dep[key] = {'reqs': reqs, 'outs': outs}

    total_reqs = sum(d['reqs'].sum() for d in per_dep.values())
    total_outs = sum(d['outs'].sum() for d in per_dep.values())
    if total_reqs == 0:
        logger.warning("All request counts are zero. Cannot estimate.")
        return

    overall = total_outs / total_reqs
    all_per_int = []
    for d in per_dep.values():
        r = d['reqs']
        o = d['outs']
        n = min(len(r), len(o))
        if n:
            all_per_int.extend((o[:n] / np.where(r[:n] != 0, r[:n], 1)).tolist())
    df_all = pd.Series(all_per_int, dtype=float) if all_per_int else pd.Series([], dtype=float)
    stats_all = {
        'overall_avg': overall,
        'minute_avg': df_all.mean() if not df_all.empty else 0.0,
        'minute_min': df_all.min() if not df_all.empty else 0.0,
        'minute_max': df_all.max() if not df_all.empty else 0.0,
        'minute_std': df_all.std() if not df_all.empty else 0.0,
        'minute_p95': df_all.quantile(0.95) if not df_all.empty else 0.0,
        'minute_p99': df_all.quantile(0.99) if not df_all.empty else 0.0,
    }

    print(f"Estimated completion tokens per request for time period {start.date()} to {end.date()} at {args.granularity_mins}-minute granularity:")
    for k, v in stats_all.items():
        print(f"{k:12}: {v:.2f}")

    print("\nBreakdown by model deployment (sorted by request count):")
    for key in sorted(per_dep.keys(), key=lambda k: per_dep[k]['reqs'].sum(), reverse=True):
        r = per_dep[key]['reqs']
        o = per_dep[key]['outs']
        tot_r = float(r.sum())
        if tot_r == 0:
            continue
        n = min(len(r), len(o))
        per_int = (o[:n] / np.where(r[:n] != 0, r[:n], 1)) if n else np.array([])
        s = pd.Series(per_int)
        stats_dep = {
            'overall_avg': float(o.sum()) / tot_r,
            'minute_avg': float(s.mean()) if not s.empty else 0.0,
            'minute_min': float(s.min()) if not s.empty else 0.0,
            'minute_max': float(s.max()) if not s.empty else 0.0,
            'minute_std': float(s.std()) if not s.empty else 0.0,
            'minute_p95': float(s.quantile(0.95)) if not s.empty else 0.0,
            'minute_p99': float(s.quantile(0.99)) if not s.empty else 0.0,
        }
        print(f"- Deployment: {key}")
        for fk in ['overall_avg','minute_avg','minute_min','minute_max','minute_std','minute_p95','minute_p99']:
            print(f"    {fk:12}: {stats_dep[fk]:.2f}")


if __name__ == '__main__':
    main()
