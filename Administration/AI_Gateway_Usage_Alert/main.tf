terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "email_address" {
  description = "(Required) Email or distribution list that should receive the AI gateway usage alert."
  type        = string
}

variable "ai_gateway_resource_id" {
  description = "(Required) Resource ID of the Azure API Management service hosting the AI gateway logs to monitor."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that stores the monitoring resources created by this example."
  type        = string
  default     = "ai_gateway_usage_alert_rg"
}

variable "resource_group_location" {
  description = "Azure region for the monitoring resource group and Log Analytics workspace."
  type        = string
  default     = "East US2"
}

variable "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace queried by the alert."
  type        = string
  default     = "ai-gateway-usage-law"
}

variable "log_analytics_retention_in_days" {
  description = "Retention period for Log Analytics data."
  type        = number
  default     = 30
}

variable "action_group_name" {
  description = "Name of the Azure Monitor action group."
  type        = string
  default     = "ai-gateway-usage-ag"
}

variable "action_group_short_name" {
  description = "Short name for the Azure Monitor action group. Must be 12 characters or fewer."
  type        = string
  default     = "aigwalert"
}

variable "alert_name" {
  description = "Name of the scheduled query alert."
  type        = string
  default     = "ai-gateway-token-usage-spike"
}

variable "alert_severity" {
  description = "Alert severity where 0 is highest and 4 is lowest."
  type        = number
  default     = 2
}

variable "app_id_header_name" {
  description = "Request header name that carries the caller application ID used to segment token usage."
  type        = string
  default     = "appid"
}

variable "min_total_tokens_in_window" {
  description = "Minimum total tokens for a single app ID in the current 10-minute window before the spike alert can trigger."
  type        = number
  default     = 100000
}

variable "spike_multiplier" {
  description = "Required multiplier over the historical 95th percentile of 10-minute token usage for the same app ID."
  type        = number
  default     = 1.5
}

variable "notification_throttle_minutes" {
  description = "Suppress repeat notifications for this many minutes after the alert fires."
  type        = number
  default     = 60
}

locals {
  common_tags = {
    workload = "ai-gateway"
    signal   = "token-usage"
  }

  ai_gateway_usage_spike_query = <<-QUERY
    let window = 10m;
    let baseline_lookback = 1d - window;
    let current_window_end = bin(now(), window);
    let current_window_start = current_window_end - window;
    let all_windows = range WindowStart from current_window_start - baseline_lookback to current_window_start step window;
    let gateway_requests =
        ApiManagementGatewayLogs
        | where _ResourceId =~ "${var.ai_gateway_resource_id}"
        | where TimeGenerated >= current_window_start - baseline_lookback and TimeGenerated < current_window_end
        // Segment traffic by the caller app ID captured in a request header.
        | extend RawAppId = tostring(parse_json(tostring(RequestHeaders))["${var.app_id_header_name}"])
        | extend AppId = trim(@"[ \[\]\"]+", RawAppId)
        | where isnotempty(CorrelationId) and isnotempty(AppId)
        | summarize AppId = take_any(AppId) by CorrelationId;
    let token_windows =
        ApiManagementGatewayLlmLog
        | where _ResourceId =~ "${var.ai_gateway_resource_id}"
        | where TimeGenerated >= current_window_start - baseline_lookback and TimeGenerated < current_window_end
        | where isnotempty(CorrelationId)
        | extend InteractionId = coalesce(CorrelationId, RequestId)
        // Deduplicate request, response, and chunk rows for the same LLM interaction.
        | summarize RequestTokens = max(tolong(TotalTokens)) by CorrelationId, InteractionId, WindowStart = bin(TimeGenerated, window)
        | join kind=inner gateway_requests on CorrelationId
        | summarize TokensPerWindow = sum(RequestTokens) by AppId, WindowStart;
    let app_ids =
        token_windows
        | summarize by AppId;
    let filled_windows =
        app_ids
        | extend JoinKey = 1
        | join kind=inner (all_windows | extend JoinKey = 1) on JoinKey
        | project AppId, WindowStart
        | join kind=leftouter token_windows on AppId, WindowStart
        | project AppId, WindowStart, TokensPerWindow = tolong(coalesce(TokensPerWindow, 0));
    let baseline =
        filled_windows
        | where WindowStart < current_window_start
        | summarize BaselineP95Tokens = percentile(TokensPerWindow, 95), BaselineAvgTokens = avg(TokensPerWindow) by AppId;
    let current =
        filled_windows
        | where WindowStart == current_window_start
        | project AppId, Current10MinTokens = TokensPerWindow;
    baseline
    | join kind=inner current on AppId
    | extend
        Current10MinTokens = tolong(coalesce(Current10MinTokens, 0)),
        BaselineP95Tokens = tolong(coalesce(BaselineP95Tokens, 0)),
        BaselineAvgTokens = round(todouble(coalesce(BaselineAvgTokens, 0)), 2)
    | extend SpikeRatio = round(
        todouble(Current10MinTokens) / iif(BaselineP95Tokens == 0, 1.0, todouble(BaselineP95Tokens)),
        2
      )
    | where Current10MinTokens >= ${var.min_total_tokens_in_window}
    | where SpikeRatio >= ${var.spike_multiplier}
    | project
        TimeGenerated = current_window_end,
        AppId,
        AggregatedValue = Current10MinTokens,
        Current10MinTokens,
        BaselineP95Tokens,
        BaselineAvgTokens,
        SpikeRatio
  QUERY
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "monitoring" {
  name     = var.resource_group_name
  location = var.resource_group_location

  tags = local.common_tags
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = var.log_analytics_workspace_name
  location            = azurerm_resource_group.monitoring.location
  resource_group_name = azurerm_resource_group.monitoring.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_in_days

  tags = local.common_tags
}

resource "azurerm_monitor_action_group" "email_group" {
  name                = var.action_group_name
  resource_group_name = azurerm_resource_group.monitoring.name
  short_name          = var.action_group_short_name

  email_receiver {
    name          = "ai-gateway-admin-email"
    email_address = var.email_address
  }

  tags = local.common_tags
}

resource "azurerm_monitor_scheduled_query_rules_alert" "ai_gateway_usage_spike" {
  name                = var.alert_name
  location            = azurerm_log_analytics_workspace.law.location
  resource_group_name = azurerm_resource_group.monitoring.name

  action {
    action_group  = [azurerm_monitor_action_group.email_group.id]
    email_subject = "AI gateway token usage spike detected by app ID"
  }

  data_source_id = azurerm_log_analytics_workspace.law.id
  description    = "Alert when the last completed 10-minute AI gateway token usage window for a single app ID spikes above historical norms."
  enabled        = true
  query_type     = "ResultCount"
  severity       = var.alert_severity
  frequency      = 10
  time_window    = 1440
  throttling     = var.notification_throttle_minutes
  query          = local.ai_gateway_usage_spike_query

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }

  tags = local.common_tags
}
