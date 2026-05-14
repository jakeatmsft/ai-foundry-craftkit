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
  default     = "ai-gateway-token-spike"
}

variable "alert_severity" {
  description = "Alert severity where 0 is highest and 4 is lowest."
  type        = number
  default     = 2
}

variable "api_id" {
  description = "APIM API identifier to scope the alert (e.g. v2-azure-openai-service-api)."
  type        = string
  default     = "v2-azure-openai-service-api"
}

variable "anomaly_threshold" {
  description = "Sensitivity for series_decompose_anomalies — number of standard deviations from the seasonal baseline that constitutes an anomaly. Lower values are more sensitive."
  type        = number
  default     = 2.5
}

variable "lookback_days" {
  description = "Number of days of history used to build the per-subscription-ID baseline time series."
  type        = number
  default     = 14
}

variable "bin_size_minutes" {
  description = "Time series bin size in minutes. Must match the alert frequency."
  type        = number
  default     = 60
}

variable "recent_window_minutes" {
  description = "How far back from now to look for anomalies when the alert evaluates. Should equal bin_size_minutes."
  type        = number
  default     = 60
}

variable "notification_throttle_minutes" {
  description = "Suppress repeat notifications for this many minutes after the alert fires."
  type        = number
  default     = 60
}

variable "app_email_map" {
  description = "Map of ApimSubscriptionId to email recipients; include a default key."
  type        = map(list(string))
  default = {
    default = ["ai-gateway-admins@example.com"]
  }
}

variable "logic_app_name" {
  description = "Name of the Logic App that routes alerts to email recipients by AppId."
  type        = string
  default     = "ai-gateway-alert-router"
}

variable "router_action_group_name" {
  description = "Name of the shared action group that triggers the alert router Logic App."
  type        = string
  default     = "ai-gateway-router-ag"
}

locals {
  common_tags = {
    workload = "ai-gateway"
    signal   = "token-anomaly"
  }

  ai_gateway_token_spike_query = <<-QUERY
    let lookback        = ${var.lookback_days}d;
    let binSize         = ${var.bin_size_minutes}m;
    let anomalyThreshold = ${var.anomaly_threshold};
    let recentWindow    = ${var.recent_window_minutes}m;
    ApiManagementGatewayLogs
    | where _ResourceId =~ "${var.ai_gateway_resource_id}"
    | where TimeGenerated >= ago(lookback)
    | where ApiId == "${var.api_id}"
    | where IsRequestSuccess == true
    | where Url has "/deployments/"
    | parse Url with * "/deployments/" model_deployment_name "/" *
    | where isnotempty(model_deployment_name)
    | project TimeGenerated, CorrelationId, ApimSubscriptionId
    | join hint.strategy=broadcast kind=inner (
      ApiManagementGatewayLlmLog
      | where _ResourceId =~ "${var.ai_gateway_resource_id}"
      | where TimeGenerated >= ago(lookback)
      | where SequenceNumber == 0
      | project CorrelationId, TotalTokens
    ) on CorrelationId
    | summarize total_tokens = sum(TotalTokens)
      by bin(TimeGenerated, binSize), ApimSubscriptionId
    | make-series
      tokens_series = sum(total_tokens) default=0
      on TimeGenerated from ago(lookback) to now() step binSize
      by ApimSubscriptionId
    | extend (anomalies, anomaly_score, baseline) = series_decompose_anomalies(tokens_series, anomalyThreshold)
    | mv-expand
      TimeGenerated   to typeof(datetime),
      tokens_series   to typeof(long),
      anomalies       to typeof(int),
      anomaly_score   to typeof(double),
      baseline        to typeof(double)
    | where anomalies == 1
    | where TimeGenerated >= ago(recentWindow)
    | project
      TimeGenerated,
      ApimSubscriptionId,
      total_tokens = tokens_series,
      baseline_tokens = baseline,
      anomaly_score
    | order by anomaly_score desc
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

resource "azapi_resource" "router_logic_app" {
  type      = "Microsoft.Logic/workflows@2019-05-01"
  name      = var.logic_app_name
  parent_id = azurerm_resource_group.monitoring.id
  location  = azurerm_resource_group.monitoring.location

  body = jsonencode({
    properties = {
      state = "Enabled"
      parameters = {
        appEmailMap = {
          type         = "Object"
          defaultValue = var.app_email_map
        }
      }
      definition = {
        "$schema"       = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
        contentVersion  = "1.0.0.0"
        parameters = {
          appEmailMap = {
            type = "Object"
          }
        }
        triggers = {
          When_HTTP_request_is_received = {
            type = "Request"
            kind = "Http"
            inputs = {
              schema = {
                type = "object"
                properties = {
                  data = {
                    type = "object"
                  }
                }
              }
            }
          }
        }
        actions = {
          Parse_Alert = {
            type = "Compose"
            inputs = "@triggerBody()?['data']"
          }
          Extract_Tables = {
            type = "Compose"
            inputs = "@coalesce(outputs('Parse_Alert')?['alertContext']?['SearchResults']?['tables']?[0]?['rows'], createArray())"
            runAfter = {
              Parse_Alert = ["Succeeded"]
            }
          }
          For_each_alert_row = {
            type = "Foreach"
            foreach = "@outputs('Extract_Tables')"
            actions = {
              Extract_AppId = {
                type = "Compose"
                inputs = "@{item()?[1]}"
              }
              Resolve_Email_Recipients = {
                type = "Compose"
                inputs = "@coalesce(parameters('appEmailMap')[outputs('Extract_AppId')], parameters('appEmailMap')?['default'])"
                runAfter = {
                  Extract_AppId = ["Succeeded"]
                }
              }
              Format_Email_Body = {
                type = "Compose"
                inputs = "@concat('Subscription ID: ', outputs('Extract_AppId'), '\n', 'Time: ', item()?[0], '\n', 'Total Tokens: ', item()?[2], '\n', 'Baseline: ', item()?[3], '\n', 'Anomaly Score: ', item()?[4])"
                runAfter = {
                  Resolve_Email_Recipients = ["Succeeded"]
                }
              }
              Send_email = {
                type = "ApiConnection"
                inputs = {
                  host = {
                    connection = {
                      name = "@parameters('$connections')['office365']["value"]["connectionId"]"
                    }
                  }
                  method = "post"
                  path = "/Mail"
                  body = {
                    To = "@join(outputs('Resolve_Email_Recipients'), ';')"
                    Subject = "@concat('AI Gateway Token Spike - ', outputs('Extract_AppId'))"
                    Body = "@outputs('Format_Email_Body')"
                  }
                }
                runAfter = {
                  Format_Email_Body = ["Succeeded"]
                }
              }
            }
            runAfter = {
              Extract_Tables = ["Succeeded"]
            }
          }
        }
        outputs = {}
        parameters = {
          "$connections" = {
            defaultValue = {}
            type = "Object"
          }
        }
      }
    }
  })
}

data "azapi_resource_action" "router_callback" {
  type        = "Microsoft.Logic/workflows/triggers@2019-05-01"
  resource_id = "${azapi_resource.router_logic_app.id}/triggers/When_HTTP_request_is_received"
  action      = "listCallbackUrl"
  method      = "POST"
}

locals {
  router_callback_url = jsondecode(data.azapi_resource_action.router_callback.output).value
}

resource "azurerm_monitor_action_group" "router_ag" {
  name                = var.router_action_group_name
  resource_group_name = azurerm_resource_group.monitoring.name
  short_name          = "aigwroute"

  webhook_receiver {
    name                    = "logic-app-router"
    service_uri             = local.router_callback_url
    use_common_alert_schema = true
  }

  tags = local.common_tags
}

resource "azurerm_monitor_scheduled_query_rules_alert" "token_spike" {
  name                = var.alert_name
  location            = azurerm_log_analytics_workspace.law.location
  resource_group_name = azurerm_resource_group.monitoring.name

  action {
    action_group  = [azurerm_monitor_action_group.router_ag.id]
    email_subject = "AI Gateway: Anomalous token consumption by subscription"
  }

  data_source_id = azurerm_log_analytics_workspace.law.id
  description    = "Alert when a subscription ID exhibits anomalous token consumption relative to its historical baseline."
  enabled        = true
  query_type     = "ResultCount"
  severity       = var.alert_severity
  frequency      = var.bin_size_minutes
  time_window    = 1440
  throttling     = var.notification_throttle_minutes
  query          = local.ai_gateway_token_spike_query

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }

  tags = local.common_tags
}

output "router_logic_app_url" {
  description = "HTTP trigger URL of the alert router Logic App."
  value       = local.router_callback_url
  sensitive   = true
}

output "router_action_group_id" {
  description = "Resource ID of the shared router action group."
  value       = azurerm_monitor_action_group.router_ag.id
}
