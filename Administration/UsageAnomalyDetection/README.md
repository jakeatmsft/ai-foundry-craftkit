# Usage Anomaly Detection

This folder contains Terraform and KQL assets to detect APIM usage anomalies for Azure OpenAI traffic.

## Files

- `tfe_template.tf`: Deploys a native Terraform scheduled query alert rule.
- `anomaly_detect.kql`: KQL logic used to detect token anomalies by `ApimSubscriptionId`.

## What is configured

- Alert evaluation frequency: `PT1H` (every hour)
- Alert rule window: `1440` minutes (provider limit-friendly); the KQL still uses a `14d` lookback to build its baseline
- Query start time: `let startDate = now();` (current execution time)
- Lookback for baseline: `14d`
- Bin size: `1h`
- Alert type: scheduled query `ResultCount`
- Alert condition intent: any query result indicates an anomaly (`ResultCount > 0`)

## Notes

- The query currently filters to `ApimSubscriptionId contains "107309"`. Update this filter if you want broader coverage.
- The query computes its own anomaly score with `series_decompose_anomalies`, so the alert should stay on a standard scheduled-query rule instead of an Azure Monitor dynamic-threshold rule.

## Validate locally

From this folder:

```powershell
terraform fmt
terraform validate
```
