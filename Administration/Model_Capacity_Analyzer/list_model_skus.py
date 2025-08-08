#!/usr/bin/env python3
"""
List available Azure OpenAI models and their SKU capacity (min, max, default) for a given account.
"""
import os
import argparse
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, DeviceCodeCredential, ChainedTokenCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

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

    # Management client for account info
    mgmt = CognitiveServicesManagementClient(credential, sub_id)
    account = mgmt.accounts.get(rg, account_name)
    region = account.location
    logger.debug(f'Account region: {region}')

    # Acquire token for ARM
    try:
        token = credential.get_token('https://management.azure.com/.default').token
    except Exception:
        token = device_cred.get_token('https://management.azure.com/.default').token

    # Build List Models endpoint
    url = (
        f'https://management.azure.com/subscriptions/{sub_id}'
        f'/providers/Microsoft.CognitiveServices/locations/{region}/models'
        f'?api-version=2024-10-01'
    )
    logger.info(f'Listing models via: {url}')

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    models = response.json().get('value', [])

    # Extract SKU capacities
    rows = []
    for m in models:
        mdl = m.get('model', {})
        name = mdl.get('name')
        version = mdl.get('version')
        skus = mdl.get('skus', [])
        for sku in skus:
            cap = sku.get('capacity', {})
            rows.append({
                'model': name,
                'version': version,
                'sku': sku.get('name'),
                'min': cap.get('minimum'),
                'max': cap.get('maximum'),
                'default': cap.get('default'),
            })

    # Print table
    if not rows:
        logger.warning('No models or SKUs found.')
        return
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))
    except ImportError:
        # Fallback to manual printing
        header = ['Model', 'Version', 'SKU', 'Min', 'Max', 'Default']
        print('  '.join(header))
        for r in rows:
            print(f"{r['model']:10}  {r['version']:8}  {r['sku']:10}  {r['min']:>5}  {r['max']:>5}  {r['default']:>7}")

if __name__ == '__main__':
    main()