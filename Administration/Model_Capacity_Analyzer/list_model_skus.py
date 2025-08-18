#!/usr/bin/env python3
"""
List available capacity for each Azure OpenAI model SKU across all regions using the usages API.
"""
import os
import argparse
import logging
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, DeviceCodeCredential, ChainedTokenCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
import re

def main():
    parser = argparse.ArgumentParser(description="List model SKUs and capacities.")
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    # Load environment variables
    load_dotenv()
    sub_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    rg = os.getenv('AZURE_RESOURCE_GROUP_NAME')
    account_name = os.getenv('AZURE_AOAI_RESOURCE_NAME')
    if not all([sub_id, rg, account_name]):
        logger.error('Environment variables AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP_NAME, and AZURE_AOAI_RESOURCE_NAME must be set')
        return

    # Authenticate with fallback
    base_cred = DefaultAzureCredential()
    device_cred = DeviceCodeCredential(tenant_id=os.getenv('AZURE_TENANT_ID', None))
    credential = ChainedTokenCredential(base_cred, device_cred)

    # Management client (not needed for region list)
    api_ver = '2023-05-01'
    # Acquire token for ARM

    try:
        token = credential.get_token('https://management.azure.com/.default').token
    except Exception:
        token = device_cred.get_token('https://management.azure.com/.default').token
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
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

    # Gather usage capacities per SKU for each region
    rows = []
    for region in regions:
        usage_url = (
            f'https://management.azure.com/subscriptions/{sub_id}'
            f'/providers/Microsoft.CognitiveServices/locations/{region}'
            f'/usages?api-version={api_ver}'
        )
        logger.debug(f'Fetching usage for region: {region}')
        resp = requests.get(usage_url, headers=headers)
        if not resp.ok:
            logger.warning(f'Could not fetch usages for region {region}: {resp.status_code}')
            continue
        usages = resp.json().get('value', [])
        for u in usages:
            nm = u.get('name', {})
            sku_val = nm.get('value') or ''
            # parse SKUs of form <namespace>.<tier>.<ModelName> via regex
            m = re.match(r'^[^.]+\.[^.]+\.(.+)$', sku_val)
            model = m.group(1) if m else sku_val
            limit = u.get('limit')
            used = u.get('currentValue')
            available = (limit - used) if (limit is not None and used is not None) else None
            rows.append({
                'region': region,
                'model': model,
                'sku': sku_val,
                'limit': limit,
                'used': used,
                'available': available,
                'unit': u.get('unit')
            })

    # Print table of available capacities
    if not rows:
        logger.warning('No model SKU usages found.')
        return
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))
    except ImportError:
        # Fallback to manual printing
        header = ['Region', 'Model', 'SKU', 'Limit', 'Used', 'Available', 'Unit']
        print('  '.join(header))
        for r in rows:
            region = r.get('region', '')
            lm = r.get('limit') if r.get('limit') is not None else ''
            used = r.get('used') if r.get('used') is not None else ''
            avail = r.get('available') if r.get('available') is not None else ''
            unit = r.get('unit', '')
            print(
                f"{region:15}  {r['model']:20}  {r['sku']:30}  {lm:6}  {used:6}  {avail:9}  {unit}"
            )

if __name__ == '__main__':
    main()