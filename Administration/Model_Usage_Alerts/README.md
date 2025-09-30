# Azure OpenAI Provisioned Utilization Alert Script

This folder contains `create_openai_utilization_alert.sh`, a helper script that provisions an Azure Monitor metric alert for Azure OpenAI deployments. The alert watches the `AzureOpenAIProvisionedManagedUtilizationV2` metric and fires when utilization for a specific deployment reaches or exceeds 90%, which is the point at which throttling (HTTP 429) can start.

## Prerequisites

- Azure CLI 2.52.0 or newer with the `monitor` extension (install on first run if prompted).
- An Azure subscription with an existing Azure OpenAI (Cognitive Services) account and a named deployment.
- Permission to create Azure Monitor alert rules and action groups in the target resource group.
- Authenticated Azure CLI session (`az login`) in the correct subscription/tenant.

## Usage

Run the script from Bash in Azure Cloud Shell or any environment with the Azure CLI available.

```bash
./create_openai_utilization_alert.sh \
  --resource-group <rg-name> \
  --account <aoai-account-name> \
  --deployment <deployment-name> \
  --action-group-rg <rg-for-action-group> \
  --action-group-name <action-group-name> \
  --action-group-email <recipient@example.com>
```

You can also drive the script with environment variables:

```bash
RESOURCE_GROUP="rg-ai" \
AOAI_ACCOUNT="contoso-openai" \
DEPLOYMENT_NAME="gpt-4o" \
ACTION_GROUP_RG="rg-ai" \
ACTION_GROUP_NAME="aoai-alerts" \
ACTION_GROUP_EMAIL="oncall@contoso.com" \
./create_openai_utilization_alert.sh
```

If you already have an action group you want to reuse, provide its resource ID instead of the action group creation parameters:

```bash
./create_openai_utilization_alert.sh \
  --resource-group rg-ai \
  --account contoso-openai \
  --deployment gpt-4o \
  --action-group-id "/subscriptions/<sub>/resourceGroups/rg-ai/providers/microsoft.insights/actionGroups/aoai-alerts"
```

## Parameters

| Flag / Variable | Required | Description |
|-----------------|----------|-------------|
| `--resource-group` / `RESOURCE_GROUP` | Yes | Resource group that hosts the Azure OpenAI account. |
| `--account` / `AOAI_ACCOUNT` | Yes | Name of the Azure OpenAI (Cognitive Services) account. |
| `--deployment` / `DEPLOYMENT_NAME` | Yes | Azure OpenAI deployment to monitor (used in the `ModelDeploymentName` dimension filter). |
| `--alert-name` / `ALERT_NAME` | No | Alert rule name (default: `aoai-provisioned-utilization-alert`). |
| `--action-group-id` / `ACTION_GROUP_ID` | Conditional | Resource ID of an existing action group. Required if you do not supply creation parameters. |
| `--action-group-rg` / `ACTION_GROUP_RG` | Conditional | Resource group containing the action group to create or reuse. Required when `ACTION_GROUP_ID` is omitted. |
| `--action-group-name` / `ACTION_GROUP_NAME` | Conditional | Action group name to create or reuse when `ACTION_GROUP_ID` is omitted. |
| `--action-group-email` / `ACTION_GROUP_EMAIL` | Conditional | Email recipient used when creating a new action group. |
| `--action-group-short` / `ACTION_GROUP_SHORT_NAME` | No | Short name for the action group (default: `AOAIUtil`, must be ≤12 characters). |
| `--severity` / `SEVERITY` | No | Alert severity from 1 (critical) to 4 (informational). Default is `2`. |
| `--evaluation-frequency` / `EVALUATION_FREQUENCY` | No | ISO8601 frequency for re-evaluation (default: `PT1M`). |
| `--window-size` / `WINDOW_SIZE` | No | ISO8601 lookback window for metric aggregation (default: `PT5M`). |

## What the Script Does

1. Optionally creates or locates an action group and captures its resource ID.
2. Resolves the resource ID for the Azure OpenAI account scope.
3. Builds a dimension filter targeting the provided deployment name.
4. Creates a metric alert condition on the `AzureOpenAIProvisionedManagedUtilizationV2` metric with a 90% threshold and `Maximum` aggregation.
5. Creates or updates an Azure Monitor metric alert rule that evaluates every minute over a five-minute window.

## Verification and Cleanup

- Confirm the alert exists: `az monitor metrics alert show --name <alert-name> --resource-group <rg-name>`
- Trigger a test notification from the action group to validate routing (for email channels use the Azure Portal or `az monitor action-group test-notifications`).
- To delete the alert when no longer needed: `az monitor metrics alert delete --name <alert-name> --resource-group <rg-name>`
- Remove test action groups if they were created specifically for evaluation: `az monitor action-group delete --name <action-group-name> --resource-group <rg-name>`

## Example One-liner

```bash
az monitor metrics alert create \
    --name aoai-provisioned-utilization-alert \
    --resource-group sc1-oai \
    --scopes "/subscriptions/<subid>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<accountid>" \
    --condition "max AzureOpenAIProvisionedManagedUtilizationV2 >= 90 where ModelDeploymentName includes '<deploymentname>'" \
    --window-size PT5M \
    --evaluation-frequency PT1M \
    --severity 2 \
    --description "Azure OpenAI deployment gpt-4.1 utilization >= 90%" \
    --action "/subscriptions/<subid>/resourceGroups/<rg>/providers/microsoft.insights/actionGroups/<action_group_name>"
``` 
