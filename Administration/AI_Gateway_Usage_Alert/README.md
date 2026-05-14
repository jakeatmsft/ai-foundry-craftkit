# AI Gateway Token Anomaly Alert with Subscription Routing

This Terraform configuration detects anomalous token consumption spikes from Azure API Management AI gateway logs and routes notifications to subscription owners via email.

The architecture uses:
- **Log Analytics**: collects AI gateway and LLM logs
- **Scheduled Query Alert**: runs a KQL anomaly detection rule on token consumption trends per subscription ID
- **Shared Action Group**: routes all alerts to a webhook
- **Logic App (Consumption)**: parses alerts, looks up subscription → email mappings, and sends emails
- **No storage account required**: Logic App Consumption is a serverless event handler

## Architecture

![AI Gateway Token Anomaly Alert with Subscription Routing](https://aka.ms/azure/api-management/ai-gateway/anomaly-alerts/ai-gateway-token-anomaly-alert-with-subscription-routing.png)

## What it creates

- A resource group for monitoring resources
- A Log Analytics workspace
- An email-based Azure Monitor action group
- A scheduled query alert for AI gateway token spikes

## Important prerequisite

Your Azure API Management instance must already be sending both **Logs related to generative AI gateway** and **Logs related to ApiManagement Gateway** to the Log Analytics workspace used by this configuration. Without both diagnostic categories, the join between `ApiManagementGatewayLlmLog` and `ApiManagementGatewayLogs` will not work.

This query assumes the caller application ID is available in the request headers under `appid` by default. If you stamp the app ID into a different header, change `app_id_header_name`.

For this scheduled query alert pattern, make sure both `ApiManagementGatewayLlmLog` and `ApiManagementGatewayLogs` are using the `Analytics` plan in the target workspace. Both tables are Basic-log capable, and Azure Monitor documents Basic-log support under simple log alerts instead of standard scheduled query alerts. If needed, switch the table plans after the tables exist:

```bash
az monitor log-analytics workspace table update \
  --resource-group <workspace-rg> \
  --workspace-name <workspace-name> \
  --name ApiManagementGatewayLlmLog \
  --plan Analytics

az monitor log-analytics workspace table update \
  --resource-group <workspace-rg> \
  --workspace-name <workspace-name> \
  --name ApiManagementGatewayLogs \
  --plan Analytics
```

## Inputs

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `email_address` | Yes | Email or distribution list to notify. | n/a |
| `ai_gateway_resource_id` | Yes | Resource ID of the Azure API Management service whose AI gateway logs should be monitored. | n/a |
| `resource_group_name` | No | Resource group that stores the monitoring resources. | `ai_gateway_usage_alert_rg` |
| `resource_group_location` | No | Azure region for the monitoring resources. | `East US2` |
| `log_analytics_workspace_name` | No | Log Analytics workspace name. | `ai-gateway-usage-law` |
| `log_analytics_retention_in_days` | No | Log retention in days. | `30` |
| `action_group_name` | No | Action group name. | `ai-gateway-usage-ag` |
| `action_group_short_name` | No | Action group short name, max 12 chars. | `aigwalert` |
| `alert_name` | No | Alert rule name. | `ai-gateway-token-usage-spike` |
| `alert_severity` | No | Alert severity from 0 to 4. | `2` |
| `app_id_header_name` | No | Request header name used to read the app ID. | `appid` |
| `min_total_tokens_in_window` | No | Minimum tokens for one app ID in the current 10-minute window before the alert can trigger. | `100000` |
| `spike_multiplier` | No | Required multiple over the historical 95th percentile for the same app ID. | `1.5` |
| `notification_throttle_minutes` | No | Suppress repeated notifications after a fire. | `60` |

## Usage

1. Copy [terraform.tfvars.example](/mnt/c/repo/ai-foundry-craftkit/Administration/AI_Gateway_Usage_Alert/terraform.tfvars.example) to `terraform.tfvars` and update the values.
2. Initialize Terraform:

   ```bash
   terraform init
   ```

3. Review the plan:

   ```bash
   terraform plan
   ```

4. Apply the configuration:

   ```bash
   terraform apply
   ```

## Alert logic

The KQL query:

- Reads `ApiManagementGatewayLlmLog`
- Reads `ApiManagementGatewayLogs` to extract an app ID from request headers
- Filters to one API Management AI gateway using `_ResourceId`
- Joins gateway logs and LLM logs on `CorrelationId`
- Deduplicates multiple rows for the same LLM interaction
- Sums `TotalTokens` into 10-minute buckets per app ID
- Compares the last completed 10-minute bucket with the historical 95th percentile for the same app ID
- Returns a result only when the current window exceeds both `min_total_tokens_in_window` and `spike_multiplier * historical_p95`

Tune `min_total_tokens_in_window` and `spike_multiplier` for your workload so normal burstiness does not generate noise.
