#!/usr/bin/env python3
"""
Estimate expected completion (output) tokens per OpenAI model request using 30-day historical metrics.
"""
import os
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import numpy as np
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.monitor.query import MetricsQueryClient
import logging

def main():
    # CLI arguments
    parser = argparse.ArgumentParser(
        description="Estimate expected completion tokens per model request.")
    parser.add_argument('--debug', action='store_true', help='Enable debug logs')
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    # Load environment
    load_dotenv()
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    rg = os.getenv('AZURE_RESOURCE_GROUP_NAME')
    resource_name = os.getenv('AZURE_AOAI_RESOURCE_NAME')
    if not all([subscription_id, rg, resource_name]):
        raise ValueError("AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP_NAME, AZURE_AOAI_RESOURCE_NAME must be set")

    # Build resource URI
    resource_id = (
        f"/subscriptions/{subscription_id}/resourceGroups/{rg}"
        f"/providers/Microsoft.CognitiveServices/accounts/{resource_name}"
    )
    logger.debug(f"Resource ID: {resource_id}")

    # Authenticate
    credential = DefaultAzureCredential()
    client = MetricsQueryClient(credential)

    # Define timespan: last 30 days
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    logger.info(f"Querying metrics from {start.date()} to {end.date()}")

    # Metrics: total model requests and total output tokens
    metrics = ['ModelRequests', 'GeneratedTokens']
    try:
        resp = client.query_resource(
            resource_uri=resource_id,
            metric_names=metrics,
            timespan=(start, end),
            granularity=timedelta(days=1),
            aggregations=['Total'],
        )
    except Exception as ex:
        logger.error(f"Failed to query metrics: {ex}")
        return

    # Extract time series
    data = {}
    for m in resp.metrics:
        # flatten all time points
        vals = [pt.total or 0 for ts in m.timeseries for pt in ts.data]
        data[m.name] = np.array(vals)
        logger.debug(f"{m.name} values: {data[m.name]}")

    reqs = data.get('ModelRequests', np.array([]))
    outs = data.get('GeneratedTokens', np.array([]))
    # Ensure arrays have matching lengths and non-zero data
    # Truncate to shortest length to align per-day data
    print("Request counts:", reqs)
    print("Output tokens:", outs)
    n = min(len(reqs), len(outs))
    if n == 0:
        logger.warning("Insufficient data for requests or output tokens. Cannot estimate.")
        return
    reqs = reqs[:n]
    outs = outs[:n]
    if reqs.sum() == 0:
        logger.warning("All request counts are zero. Cannot estimate.")
        return

    # Daily per-request completion tokens
    per_day = np.divide(
        outs, reqs, out=np.zeros_like(outs, dtype=float), where=reqs!=0)

    # Aggregate statistics
    overall = outs.sum() / reqs.sum()
    df = pd.Series(per_day)
    daily_p95 = df.quantile(0.95)
    # To account for outliers and avoid underestimation, use the 95th percentile as the recommended estimate
    recommended_estimate = daily_p95
    stats = {
        #'recommended_tokens': recommended_estimate,
        'overall_avg': overall,
        'daily_avg': df.mean(),
        'daily_min': df.min(),
        'daily_max': df.max(),
        'daily_std': df.std(),
        'daily_p95': daily_p95,
        'daily_p99': df.quantile(0.99),
    }
    # Print results
    print(f"Estimated completion tokens per request for time period {start.date()} to {end.date()}:")
    for k, v in stats.items():
        print(f"{k:12}: {v:.2f}")

if __name__ == '__main__':
    main()