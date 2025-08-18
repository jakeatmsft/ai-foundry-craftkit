# Model Capacity Analyzer

This directory contains scripts to analyze Azure OpenAI model quotas and compare them against deployed capacities in your Azure Cognitive Services account.

## Prerequisites
- Python 3.7 or higher
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
### list_model_skus.py
Requires:
```dotenv
AZURE_SUBSCRIPTION_ID=<your subscription id>
AZURE_RESOURCE_GROUP_NAME=<your resource group name>
AZURE_AOAI_RESOURCE_NAME=<your Cognitive Services account name>
AZURE_TENANT_ID=<your tenant id>  # optional, for DeviceCodeCredential fallback
```

### compare_deployments_to_quota.py
Requires:
```dotenv
AZURE_SUBSCRIPTION_ID=<your subscription id>
AZURE_TENANT_ID=<your tenant id>  # optional, for DeviceCodeCredential fallback
```

## Scripts

### list_model_skus.py
Lists available Azure OpenAI models and their SKU capacity (min, max, default) for the specified account.

Usage:
```bash
python list_model_skus.py [--debug]
```

### compare_deployments_to_quota.py
Compares the granted quota for each model SKU against the sum of deployed capacities in your account.

Usage:
```bash
python compare_deployments_to_quota.py [--debug]
```

By default, this script writes results to a CSV file named `quota_comparison_<YYYYMMDD_HHMMSS>.csv` in the current directory, in addition to printing the table.

Output columns:
- subscription: Azure subscription ID
- region: Azure region
- resource: Name(s) of Azure OpenAI account(s) hosting the deployment(s)
- deployment: Deployment name(s)
- model: Model name (e.g., ada)
- version: Model version
- sku: SKU name (e.g., Standard)
- deployed: Total deployed capacity for the SKU
- limit: Total quota limit as reported by the Azure usages API
- used: Current usage from the Azure usages API
- available: Remaining quota (limit minus used)
- status: One of:
  - `OK`: available ≥ 0
  - `NO_QUOTA_INFO`: no usage info available for this SKU/region
  - `MAX_DEPLOYED`: available <= 0