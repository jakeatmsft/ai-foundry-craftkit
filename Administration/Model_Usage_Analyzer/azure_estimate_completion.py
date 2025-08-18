
#!/usr/bin/env python3
"""
Estimate expected completion (output) tokens per OpenAI model request using historical Azure Monitor metrics,
with breakdown by model deployment, response-size safeguards, auto dimension detection, and CSV export.
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
from typing import Dict, List, Optional, Tuple


def is_payload_too_large_error(ex: Exception) -> bool:
    s = str(ex) if ex else ''
    s = s.lower()
    return ('exceeded maximum limit' in s) or ('response size' in s and 'exceeded' in s) or ('413' in s)


def key_from_metadata(ts, preferred_dim: str) -> str:
    mvs = getattr(ts, 'metadata_values', None) or []
    print(f"Metadata values: {mvs}")
    return mvs.get(str.lower(preferred_dim), '') if mvs else 'all'


def query_with_backoff(client: MetricsQueryClient, resource_id: str, metric_names: List[str], timespan: Tuple[datetime, datetime], granularity_mins: int, filt: Optional[str], logger: logging.Logger):
    gran = granularity_mins
    attempt = 0
    while True:
        attempt += 1
        try:
            return client.query_resource(
                resource_uri=resource_id,
                metric_names=metric_names,
                timespan=timespan,
                granularity=timedelta(minutes=gran),
                aggregations=['Total'],
                filter=filt,
            )
        except Exception as ex:
            if is_payload_too_large_error(ex) and gran < 1440:
                new_gran = min(1440, max(gran * 2, gran + 1))
                logger.warning(f"Payload too large for metrics {metric_names} at granularity {gran}m, increasing to {new_gran}m and retrying (attempt {attempt})")
                gran = new_gran
                continue
            logger.error(f"Failed to query metrics: {ex}")
            return None


def collect_coarse_totals(client: MetricsQueryClient, resource_id: str, start: datetime, end: datetime, dimension_name: str, window_days: int, coarse_gran_mins: int, req_metric_name: str, logger: logging.Logger) -> Tuple[Dict[str, float], Dict[str, set]]:
    coarse_filter = f"{dimension_name} eq '*'"
    deployment_totals: Dict[str, float] = {}
    meta_keys_values: Dict[str, set] = {}
    cur_start = start
    while cur_start < end:
        cur_end = min(cur_start + timedelta(days=window_days), end)
        resp = query_with_backoff(client, resource_id, [req_metric_name], (cur_start, cur_end), coarse_gran_mins, coarse_filter, logger)
        if resp is None:
            return {}, {}
        for m in resp.metrics:
            if m.name != req_metric_name:
                continue
            for ts in m.timeseries:
                # track metadata keys/values seen
                for mv in getattr(ts, 'metadata_values', []) or []:
                    name_obj = getattr(mv, 'name', None)
                    name_val = getattr(name_obj, 'value', None) if name_obj is not None else None
                    name = (name_val if name_val is not None else (str(name_obj) if name_obj is not None else '')).strip()
                    value = str(getattr(mv, 'value', '') or '').strip()
                    if name:
                        meta_keys_values.setdefault(name, set()).add(value)
                key = key_from_metadata(ts, dimension_name)
                total = 0.0
                for pt in ts.data:
                    total += float(getattr(pt, 'total', 0) or 0)
                deployment_totals[key] = deployment_totals.get(key, 0.0) + total
        cur_start = cur_end
    return deployment_totals, meta_keys_values


def auto_detect_dimension(client: MetricsQueryClient, resource_id: str, start: datetime, end: datetime, preferred: str, req_metric_name: str, logger: logging.Logger) -> Tuple[str, Dict[str, float], Dict[str, set]]:
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates += ['ModelDeploymentName', 'DeploymentName', 'ModelDeployment', 'ModelDeploymentId', 'Deployment', 'ModelName']
    # dedup preserving order
    seen = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]
    best_dim = preferred
    best_totals = {}
    best_meta = {}
    best_count = -1
    for dim in candidates:
        totals, meta = collect_coarse_totals(client, resource_id, start, end, dim, window_days=3, coarse_gran_mins=60, req_metric_name=req_metric_name, logger=logger)
        count = len([k for k in totals.keys() if k != 'all'])
        logger.debug(f"Probe dimension '{dim}' found {count} unique keys (excluding 'all')")
        if count > best_count:
            best_count = count
            best_dim = dim
            best_totals = totals
            best_meta = meta
        if count > 1:
            break
    return best_dim, best_totals, best_meta


def main():
    parser = argparse.ArgumentParser(description="Estimate expected completion tokens per model request.")
    parser.add_argument('--debug', action='store_true', help='Enable debug logs')
    parser.add_argument('--dimension-name', default='ModelDeploymentName', help="Azure Monitor dimension to split by (e.g., ModelDeploymentName)")
    parser.add_argument('--auto-detect-dimension', action='store_true', help='Probe common dimension names and use the one that yields multiple deployments')
    parser.add_argument('--days', type=int, default=30, help='Timespan in days to query (default: 30)')
    parser.add_argument('--granularity-mins', type=int, default=5, help='Granularity in minutes for detailed queries (default: 5)')
    parser.add_argument('--coarse-granularity-mins', type=int, default=60, help='Granularity in minutes for the coarse pass (default: 60)')
    parser.add_argument('--top-n', type=int, default=20, help='Top-N deployments to include (default: 20)')
    parser.add_argument('--window-days', type=int, default=7, help='Chunk size in days for queries (default: 7)')
    parser.add_argument('--probe-dimensions', action='store_true', help='Print the metadata keys and sample values observed during coarse pass')
    parser.add_argument('--csv-out', default=None, help='Path to write per-deployment stats CSV')
    parser.add_argument('--req-metric', default='AzureOpenAIRequests', help="Metric name for request counts (e.g., ModelRequests or AzureOpenAIRequests)")
    parser.add_argument('--tok-metric', default='GeneratedTokens', help="Metric name for generated/output tokens (e.g., GeneratedTokens or OutputTokens)")
    parser.add_argument('--debug-one-call', action='store_true', help='Make a single metrics API call and dump the raw response, then exit')
    parser.add_argument('--debug-metrics', default='auto', help="Comma-separated metric names for the debug call, or 'auto' to use req/tok metrics")
    parser.add_argument('--debug-hours', type=int, default=6, help='Hours lookback for the single debug call (default: 6)')
    parser.add_argument('--debug-interval-mins', type=int, default=5, help='Granularity minutes for the single debug call (default: 5)')
    parser.add_argument('--debug-filter', default='*', help="Dimension value for the single debug call filter. '*' means split by dimension; empty string '' means no filter")
    parser.add_argument('--debug-raw-parse', action='store_true', help='In debug-one-call mode, parse and print the raw SDK objects using __dict__ as requested')
    parser.add_argument('--debug-raw-limit', type=int, default=0, help='In debug-one-call mode, limit number of data points printed per time series (0=no limit)')
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
    dimension_name = args.dimension_name
    logger.info(
        f"Querying metrics from {start.date()} to {end.date()} split by dimension '{dimension_name}', "
        f"coarse={args.coarse_granularity_mins}m, detail={args.granularity_mins}m, top_n={args.top_n}, window_days={args.window_days}"
    )

    # If requested, make a single API call and dump the raw structure, then exit.
    if args.debug_one_call:
        dbg_metrics = [m.strip() for m in (args.debug_metrics.split(',') if args.debug_metrics else []) if m.strip()]
        if (not dbg_metrics) or (args.debug_metrics.lower() == 'auto'):
            dbg_metrics = [args.req_metric, args.tok_metric]
        dbg_end = end
        dbg_start = end - timedelta(hours=max(1, args.debug_hours))
        if args.debug_filter == '':
            dbg_filter = f"{dimension_name} eq '*'"
        else:
            val = (args.debug_filter or '').replace("'", "''")
            if val == '*':
                dbg_filter = f"{dimension_name} eq '*'"
            else:
                dbg_filter = f"{dimension_name} eq '{val}'"
        gran = max(1, args.debug_interval_mins)
        logger.info(f"DEBUG one-call: metrics={dbg_metrics}, timespan={dbg_start.isoformat()} to {dbg_end.isoformat()}, granularity={gran}m, filter={dbg_filter}")
        try:
            resp = client.query_resource(
                resource_uri=resource_id,
                metric_names=dbg_metrics,
                timespan=(dbg_start, dbg_end),
                granularity=timedelta(minutes=gran),
                aggregations=['Total'],
                filter=dbg_filter,
            )
        except Exception as ex:
            logger.error(f"DEBUG one-call failed: {ex}")
            return
        if args.debug_raw_parse:
            print("RAW dump of response.metrics:")
            for metric in getattr(resp, 'metrics', []) or []:
                try:
                    print(metric.name)
                except Exception:
                    print(metric)
                for time_series_element in getattr(metric, 'timeseries', []) or []:
                    print(getattr(time_series_element, 'metadata_values', None))
                    count = 0
                    for metric_value in getattr(time_series_element, 'data', []) or []:
                        d = getattr(metric_value, '__dict__', None)
                        if d is None:
                            try:
                                d = vars(metric_value)
                            except Exception:
                                d = str(metric_value)
                        print(d)
                        count += 1
                        if args.debug_raw_limit and count >= args.debug_raw_limit:
                            print(f"... truncated after {args.debug_raw_limit} points")
                            break
        else:
            for m in resp.metrics:
                print(f"Metric: {getattr(m, 'name', '?')} | timeseries count: {len(getattr(m, 'timeseries', []) or [])}")
                for idx, ts in enumerate(getattr(m, 'timeseries', []) or []):
                    md = []
                    for mv in getattr(ts, 'metadata_values', []) or []:
                        n = str(getattr(mv, 'name', '') or '')
                        v = str(getattr(mv, 'value', '') or '')
                        if n:
                            md.append(f"{n}={v}")
                    print(f"  TS[{idx}] metadata: {', '.join(md) if md else '(none)'}")
                    data = getattr(ts, 'data', []) or []
                    print(f"  TS[{idx}] points: {len(data)}")
                    if data:
                        sample = data if len(data) <= 6 else (data[:3] + data[-3:])
                        for j, pt in enumerate(sample):
                            t = getattr(pt, 'timestamp', None) or getattr(pt, 'time_stamp', None)
                            tot = getattr(pt, 'total', None)
                            print(f"    [{j}] t={t} total={tot}")
                        if len(data) > 6:
                            print("    ... (middle points omitted)")
        return

    # Coarse collection
    deployment_totals, meta_kv = collect_coarse_totals(client, resource_id, start, end, dimension_name, args.window_days, args.coarse_granularity_mins, args.req_metric, logger)

    # Optional auto-detect
    non_all_count = len([k for k in deployment_totals.keys() if k != 'all'])
    if (non_all_count <= 1) and args.auto_detect_dimension:
        logger.info("Auto-detecting deployment dimension name...")
        dim2, totals2, meta2 = auto_detect_dimension(client, resource_id, start, end, dimension_name, args.req_metric, logger)
        if dim2 and dim2 != dimension_name:
            logger.info(f"Using detected dimension: {dim2}")
            dimension_name = dim2
            deployment_totals, meta_kv = totals2, meta2
        else:
            logger.info("Auto-detection did not find a better dimension; continuing with current setting.")

    if args.probe_dimensions:
        print("\nObserved dimension keys and sample values from coarse pass:")
        for k, vals in sorted(meta_kv.items()):
            vals_list = sorted(list(vals))[:10]
            print(f"- {k}: {vals_list}{' ...' if len(vals) > 10 else ''}")

    print("deployments:", deployment_totals)
    sorted_deployments = [k for k,_ in sorted(((k,v) for k,v in deployment_totals.items() if k != 'all'), key=lambda kv: kv[1], reverse=True)]
    if args.top_n > 0:
        sorted_deployments = sorted_deployments[:args.top_n]
    if not sorted_deployments:
        logger.warning("No deployment dimensions returned; falling back to all")
        sorted_deployments = ['all']
    logger.info(f"Top deployments selected: {sorted_deployments}")

    def fetch_series_for_deployment(dep_key: str):
        reqs_list: List[float] = []
        outs_list: List[float] = []
        cur_start = start
        detail_gran = args.granularity_mins
        window_days = args.window_days
        while cur_start < end:
            cur_end = min(cur_start + timedelta(days=window_days), end)
            filt = f"{dimension_name} eq '{str(dep_key).replace("'", "''")}'"
            try:
                r = client.query_resource(
                    resource_uri=resource_id,
                    metric_names=[args.req_metric, args.tok_metric],
                    timespan=(cur_start, cur_end),
                    granularity=timedelta(minutes=detail_gran),
                    aggregations=['Total'],
                    filter=filt,
                )
            except Exception as ex:
                if is_payload_too_large_error(ex):
                    if detail_gran < 60:
                        new_gran = min(60, max(detail_gran * 2, detail_gran + 1))
                        logger.warning(f"Payload too large for {dep_key} at granularity {detail_gran}m; increasing to {new_gran}m and retrying window {cur_start.date()} to {cur_end.date()}")
                        detail_gran = new_gran
                        continue
                    if window_days > 1:
                        new_window = max(1, window_days // 2)
                        if new_window != window_days:
                            logger.warning(f"Payload too large for {dep_key}; reducing window from {window_days}d to {new_window}d and retrying")
                            window_days = new_window
                            continue
                logger.error(f"Failed to query metrics (detail) for {dep_key}: {ex}")
                return None, None
            reqs_win: Optional[List[float]] = None
            outs_win: Optional[List[float]] = None
            for mm in r.metrics:
                if mm.name == args.req_metric:
                    for ts in mm.timeseries:
                        arr = [float(getattr(pt, 'total', 0) or 0) for pt in ts.data]
                        if reqs_win is None:
                            reqs_win = arr
                        else:
                            n = min(len(reqs_win), len(arr))
                            reqs_win = [reqs_win[i] + arr[i] for i in range(n)]
                elif mm.name == args.tok_metric:
                    for ts in mm.timeseries:
                        arr = [float(getattr(pt, 'total', 0) or 0) for pt in ts.data]
                        if outs_win is None:
                            outs_win = arr
                        else:
                            n = min(len(outs_win), len(arr))
                            outs_win = [outs_win[i] + arr[i] for i in range(n)]
            reqs_win = reqs_win or []
            outs_win = outs_win or []
            n = min(len(reqs_win), len(outs_win))
            if n:
                reqs_list.extend(reqs_win[:n])
                outs_list.extend(outs_win[:n])
            cur_start = cur_end
        return reqs_list, outs_list

    per_deployment: Dict[str, Dict[str, np.ndarray]] = {}
    for dep in sorted_deployments:
        reqs_list, outs_list = fetch_series_for_deployment(dep)
        if reqs_list is None:
            continue
        per_deployment[dep] = {
            'reqs': np.array(reqs_list, dtype=float),
            'outs': np.array(outs_list, dtype=float),
        }

    overall_reqs_total = 0.0
    overall_outs_total = 0.0
    per_interval_all: List[float] = []
    for key, d in per_deployment.items():
        r = d['reqs']
        o = d['outs']
        if r.size == 0 or o.size == 0:
            continue
        n = min(len(r), len(o))
        r = r[:n]
        o = o[:n]
        overall_reqs_total += float(r.sum())
        overall_outs_total += float(o.sum())
        per_interval_all.extend((o / np.where(r != 0, r, 1)).tolist())

    if overall_reqs_total == 0:
        logger.warning('All request counts are zero. Cannot estimate.')
        return

    overall = overall_outs_total / overall_reqs_total
    df_all = pd.Series(per_interval_all, dtype=float) if per_interval_all else pd.Series([], dtype=float)
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

    rows: List[Dict[str, float]] = []
    print("\nBreakdown by model deployment (sorted by request count):")
    sorted_keys = sorted(per_deployment.keys(), key=lambda k: per_deployment[k]['reqs'].sum(), reverse=True)
    for key in sorted_keys:
        reqs_arr = per_deployment[key]['reqs']
        outs_arr = per_deployment[key]['outs']
        total_reqs = float(reqs_arr.sum())
        total_outs = float(outs_arr.sum())
        if total_reqs == 0:
            continue
        n = min(len(reqs_arr), len(outs_arr))
        r = reqs_arr[:n]
        o = outs_arr[:n]
        per_int = o / np.where(r != 0, r, 1)
        s = pd.Series(per_int)
        stats_dep = {
            'deployment': key,
            'total_requests': total_reqs,
            'total_generated_tokens': total_outs,
            'overall_avg': float(o.sum()) / total_reqs,
            'minute_avg': float(s.mean()),
            'minute_min': float(s.min()),
            'minute_max': float(s.max()),
            'minute_std': float(s.std()),
            'minute_p95': float(s.quantile(0.95)),
            'minute_p99': float(s.quantile(0.99)),
        }
        rows.append(stats_dep)
        print(f"- Deployment: {key}")
        for fk in ['overall_avg','minute_avg','minute_min','minute_max','minute_std','minute_p95','minute_p99']:
            print(f"    {fk:12}: {stats_dep[fk]:.2f}")

    if args.csv_out:
        try:
            df_out = pd.DataFrame(rows)
            df_out.to_csv(args.csv_out, index=False)
            print(f"Wrote per-deployment stats to: {args.csv_out}")
        except Exception as ex:
            logger.error(f"Failed to write CSV to {args.csv_out}: {ex}")


if __name__ == '__main__':
    main()
