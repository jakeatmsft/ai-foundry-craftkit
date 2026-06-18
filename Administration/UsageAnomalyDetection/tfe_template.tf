// Anomaly detection for a specific use case. The KQL computes the anomaly score,
// so this alert uses a standard scheduled query rule instead of Azure Monitor's
// dynamic-threshold criterion, which rejects queries that filter on TimeGenerated.
resource "azurerm_monitor_scheduled_query_rules_alert" "api_rate_anomaly_alert" {
  name                = "${var.rg_location_short_names[local.rg_location]}-${var.env}-api-rate-anomaly-alert-${var.resource_types.alert}"
  location            = local.rg_location
  resource_group_name = data.azurerm_resource_group.rg_details.name

  action {
    action_group  = [azurerm_monitor_action_group.action_group.id]
    email_subject = "Alert: Anomaly detected token usage- Multitenancy"
  }

  data_source_id = data.azurerm_log_analytics_workspace.common_law_details.id
  description    = "This alert is fired when API token anomalies are detected for ApimSubscriptionIds in multitenancy."
  enabled        = true
  query_type     = "ResultCount"
  severity       = 2
  frequency      = 60
  time_window    = 1440
  throttling     = 60
  query          = <<-QUERY
		let startDate = now();
		let lookback = 14d;
		let binSize = 1h;
		let anomalyThreshold = 1.1;
		let recentWindow = 1h;

		ApiManagementGatewayLogs
		| where TimeGenerated >= startDate - lookback and TimeGenerated < startDate
		| where ApimSubscriptionId contains "107309"
		| where IsRequestSuccess == true
		| where Url has "/deployments/"
		| parse Url with * "/deployments/" model_deployment_name "/" *
		| where isnotempty(model_deployment_name)
		| project TimeGenerated, CorrelationId, ApimSubscriptionId
		| join hint.strategy=broadcast kind=inner (
				ApiManagementGatewayLlmLog
				| where TimeGenerated >= startDate - lookback and TimeGenerated < startDate
				| where SequenceNumber == 0
				| project CorrelationId, TotalTokens
			) on CorrelationId
		| summarize total_tokens = sum(TotalTokens) by bin(TimeGenerated, binSize), ApimSubscriptionId
		| make-series tokens_series = sum(total_tokens) default=0 on TimeGenerated from startDate - lookback to startDate step binSize by ApimSubscriptionId
		| extend (anomalies, anomaly_score, baseline) = series_decompose_anomalies(tokens_series, anomalyThreshold)
		| mv-expand TimeGenerated to typeof(datetime), tokens_series to typeof(long), anomalies to typeof(int), anomaly_score to typeof(double), baseline to typeof(double)
		| where TimeGenerated >= startDate - recentWindow and TimeGenerated < startDate
		| where anomaly_score > 1
		| project TimeGenerated, ApimSubscriptionId, total_tokens = tokens_series, baseline_tokens = baseline, anomaly_score
		| order by anomaly_score desc
	QUERY

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }
}
