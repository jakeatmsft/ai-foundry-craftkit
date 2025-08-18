#!/usr/bin/env python3
"""
Compare deployed capacities against model quotas for Azure OpenAI accounts in a subscription.
"""
import os
import argparse
import logging
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, DeviceCodeCredential, ChainedTokenCredential
from datetime import datetime
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
import re

def main():
    parser = argparse.ArgumentParser(description="Compare deployed capacities against model quotas.")
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    load_dotenv()
    sub_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    if not sub_id:
        logger.error('Environment variable AZURE_SUBSCRIPTION_ID must be set')
        return

    base_cred = DefaultAzureCredential()
    device_cred = DeviceCodeCredential(tenant_id=os.getenv('AZURE_TENANT_ID', None))
    credential = ChainedTokenCredential(base_cred, device_cred)

    # list all Azure Cognitive Services accounts and filter OpenAI
    mgmt = CognitiveServicesManagementClient(credential, sub_id)
    try:
        accounts = list(mgmt.accounts.list())
    except Exception as e:
        logger.error(f'Failed to list Cognitive Services accounts: {e}')
        return
    openai_accounts = [a for a in accounts if getattr(a, 'kind', '') and 'OpenAI' in a.kind]
    if not openai_accounts:
        logger.error('No Azure OpenAI accounts found in subscription')
        return
    regions = set(a.location for a in openai_accounts)
    logger.debug(f'Found OpenAI accounts in regions: {regions}')

    # acquire ARM token
    try:
        token = credential.get_token('https://management.azure.com/.default').token
    except Exception:
        token = device_cred.get_token('https://management.azure.com/.default').token

    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    # fetch model quotas per region using usages API ({provider}.{tier}.{model})
    quota_map = {}
    api_ver = '2023-05-01'
    for region in regions:
        usage_url = (
            f'https://management.azure.com/subscriptions/{sub_id}'
            f'/providers/Microsoft.CognitiveServices/locations/{region}'
            f'/usages?api-version={api_ver}'
        )
        logger.info(f'Fetching quota usages for region {region}: {usage_url}')
        resp = requests.get(usage_url, headers=headers)
        resp.raise_for_status()
        for u in resp.json().get('value', []):
            nm = u.get('name', {})
            raw = nm.get('value', '')
            m = re.match(r'^([^.]+)\.([^.]+)\.(.+)$', raw)
            if m:
                provider, tier, model_name = m.groups()
            else:
                provider, tier, model_name = None, None, raw
            limit = u.get('limit')
            used = u.get('currentValue')
            available = limit - used if limit is not None and used is not None else None
            key = (sub_id, region, provider, tier, model_name)
            quota_map[key] = {'limit': limit, 'used': used, 'available': available}

    # list each deployment with its capacity and corresponding available quota
    rows = []
    for acct in openai_accounts:
        acct_id = acct.id
        account_name = acct.name
        region = acct.location
        dep_url = f'https://management.azure.com{acct_id}/deployments?api-version=2024-10-01'
        logger.info(f'Fetching deployments for account {account_name} in region {region}: {dep_url}')
        r2 = requests.get(dep_url, headers=headers)
        r2.raise_for_status()
        for d in r2.json().get('value', []):
            props = d.get('properties', {})
            mdl = props.get('model', {})
            model = mdl.get('name')
            version = mdl.get('version')
            sku = d.get('sku', {})
            sku_name = sku.get('name')
            deployed_cap = sku.get('capacity', 0) or 0
            dep_name = d.get('name')
            # match usage by provider, tier (sku_name), and model
            provider = acct.kind.split('.')[0] if acct.kind else None
            key = (sub_id, region, provider, sku_name, model)
            quota = quota_map.get(key, {})
            limit = quota.get('limit')
            used = quota.get('used')
            raw_avail = quota.get('available')  # total available from usages API
            # determine status: cannot exceed quota; mark when at or over total available
            if raw_avail is None:
                status = 'NO_QUOTA_INFO'
            elif deployed_cap >= raw_avail:
                status = 'MAX_DEPLOYED'
            else:
                status = 'OK'
            # compute remaining available capacity after this deployment
            available = raw_avail - deployed_cap if raw_avail is not None else None
            rows.append({
                'subscription': sub_id,
                'region': region,
                'resource': account_name,
                'deployment': dep_name,
                'model': model,
                'version': version,
                'sku': sku_name,
                'deployed': deployed_cap,
                'capacity': limit,
                'used': used,
                'available': available,
                'status': status,
            })

    if not rows:
        logger.info('No quotas or deployments to compare.')
        return

    # print results
    df = None
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))
    except ImportError:
        header = ['Subscription', 'Region', 'Resource', 'Deployment', 'Model', 'Version', 'SKU', 'Deployed', 'Capacity', 'Used', 'Available', 'Status']
        print('  '.join(header))
        for r in rows:
            cap = r.get('capacity') if r.get('capacity') is not None else ''
            used = r.get('used') if r.get('used') is not None else ''
            avail = r.get('available') if r.get('available') is not None else ''
            print(
                f"{r['subscription']:12}  {r['region']:10}  {r.get('resource',''):15}  {r.get('deployment',''):15}  "
                f"{r['model']:10}  {r['version']:8}  {r['sku']:10}  {r['deployed']:8}  {cap:8}  {used:8}  {avail:8}  {r['status']}"
            )

    # save to timestamped CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_name = f'quota_comparison_{timestamp}.csv'
    try:
        if df is not None:
            df.to_csv(csv_name, index=False)
        else:
            import csv
            keys = ['subscription', 'region', 'resource', 'deployment', 'model', 'version', 'sku', 'deployed', 'capacity', 'used', 'available', 'status']
            with open(csv_name, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
        logger.info(f'Saved results to {csv_name}')
    except Exception as e:
        logger.error(f'Failed to save CSV: {e}')

if __name__ == '__main__':  # pragma: no cover
    main()