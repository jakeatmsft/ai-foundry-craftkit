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

    # fetch model quotas per region
    quota_map = {}
    for region in regions:
        model_url = (
            f'https://management.azure.com/subscriptions/{sub_id}'
            f'/providers/Microsoft.CognitiveServices/locations/{region}/models'
            f'?api-version=2024-10-01'
        )
        logger.info(f'Fetching model quotas for region {region}: {model_url}')
        resp = requests.get(model_url, headers=headers)
        resp.raise_for_status()
        for m in resp.json().get('value', []):
            md = m.get('model', {})
            name = md.get('name')
            version = md.get('version')
            for sku in md.get('skus', []):
                sku_name = sku.get('name')
                cap = sku.get('capacity', {})
                key = (sub_id, region, name, version, sku_name)
                quota_map[key] = cap.get('maximum')

    # fetch deployments across all OpenAI accounts
    deployed = {}
    for acct in openai_accounts:
        # parse resource group and account name
        rg = acct.id.split('/resourceGroups/')[1].split('/')[0]
        account_name = acct.name
        region = acct.location
        dep_url = (
            f'https://management.azure.com/subscriptions/{sub_id}'
            f'/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account_name}/deployments'
            f'?api-version=2024-10-01'
        )
        logger.info(f'Fetching deployments for account {account_name} in region {region}: {dep_url}')
        r2 = requests.get(dep_url, headers=headers)
        r2.raise_for_status()
        for d in r2.json().get('value', []):
            props = d.get('properties', {})
            mdl = props.get('model', {})
            name = mdl.get('name')
            version = mdl.get('version')
            sku = d.get('sku', {})
            sku_name = sku.get('name')
            cap = sku.get('capacity', 0) or 0
            key = (sub_id, region, name, version, sku_name)
            deployed[key] = deployed.get(key, 0) + cap


    # prepare comparison rows
    rows = []
    # check deployments against quotas
    for key, dep_sum in deployed.items():
        quota = quota_map.get(key)
        status = 'OK'
        if quota is None:
            status = 'NO_QUOTA_INFO'
        elif dep_sum > quota:
            status = 'EXCEEDS_QUOTA'
        remaining = quota - dep_sum if quota is not None else None
        rows.append({
            'subscription': key[0],
            'region': key[1],
            'model': key[2],
            'version': key[3],
            'sku': key[4],
            'deployed': dep_sum,
            'quota_max': quota,
            'remaining': remaining,
            'status': status,
        })
    # also list quotas with zero deployments
    for key, quota in quota_map.items():
        if key not in deployed:
            remaining = quota if quota is not None else None
            rows.append({
                'subscription': key[0],
                'region': key[1],
                'model': key[2],
                'version': key[3],
                'sku': key[4],
                'deployed': 0,
                'quota_max': quota,
                'remaining': remaining,
                'status': 'NO_DEPLOYMENTS',
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
        header = ['Subscription', 'Region', 'Model', 'Version', 'SKU', 'Deployed', 'QuotaMax', 'Remaining', 'Status']
        print('  '.join(header))
        for r in rows:
            qm = r['quota_max'] if r['quota_max'] is not None else ''
            rem = r['remaining'] if r['remaining'] is not None else ''
            print(f"{r['subscription']:12}  {r['region']:10}  {r['model']:10}  {r['version']:8}  {r['sku']:10}  {r['deployed']:8}  {qm:8}  {rem:8}  {r['status']}")

    # save to timestamped CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_name = f'quota_comparison_{timestamp}.csv'
    try:
        if df is not None:
            df.to_csv(csv_name, index=False)
        else:
            import csv
            keys = ['subscription', 'region', 'model', 'version', 'sku', 'deployed', 'quota_max', 'remaining', 'status']
            with open(csv_name, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
        logger.info(f'Saved results to {csv_name}')
    except Exception as e:
        logger.error(f'Failed to save CSV: {e}')

if __name__ == '__main__':  # pragma: no cover
    main()