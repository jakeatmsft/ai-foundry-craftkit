terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

variable "email_address" {
  description = "(Required) The e-mail address or Distribution List that alerts should be sent to."
  type        = string
}

variable "subscriptions_list" {
  description = "Used to define the list of subscriptions, each subscription must be in the format /subscriptions/xxxxx. If this is left blank it will just create a service health alert for the current subscriptions context."
  type        = list(string)
  default     = []
}

variable "subscription_id" {
  description = "Optional override for the Azure subscription ID used by the provider. If unset, the first subscription in subscriptions_list or the active CLI context is used."
  type        = string
  default     = null
}

variable "resource_group_name" {
  description = "Defines the name of the Resource Group that the alert configuration will reside (not the scope). If left blank the default will be service_health_rg"
  type        = string
  default     = "service_health_rg"
}

variable "resource_group_location" {
  description = "The location of the Resource Group that the alert configuration will reside. If left blank the default will be East US 2"
  type        = string
  default     = "East US2"
}

locals {
  subscription_from_scope = length(var.subscriptions_list) > 0 ? (
    strcontains(var.subscriptions_list[0], "/subscriptions/") ?
    split("/", var.subscriptions_list[0])[2] :
    var.subscriptions_list[0]
  ) : null

  provider_subscription_id = var.subscription_id != null ? var.subscription_id : local.subscription_from_scope
}

provider "azurerm" {
  features {}
  subscription_id = local.provider_subscription_id
}

data "azurerm_client_config" "current" {}

locals {
  default_subscription_id = coalesce(local.provider_subscription_id, data.azurerm_client_config.current.subscription_id)
  email_address           = var.email_address
  subscriptions_list      = length(var.subscriptions_list) == 0 ? ["/subscriptions/${local.default_subscription_id}"] : var.subscriptions_list
  resource_group_name     = var.resource_group_name
  resource_group_location = var.resource_group_location
}

locals {
  common_tags = {
    environment = "Production"
  }
}

resource "azurerm_resource_group" "service_health_rg" {
  name     = local.resource_group_name
  location = local.resource_group_location

  tags = local.common_tags
}

resource "azurerm_monitor_action_group" "service_health_action_group" {
  name                = "service_health_ag"
  resource_group_name = azurerm_resource_group.service_health_rg.name
  short_name          = "shalert"

  email_receiver {
    name          = "SendToAlertDL"
    email_address = local.email_address
  }

  tags = local.common_tags
}

resource "azurerm_monitor_activity_log_alert" "main" {
  name                = "service_health_ag"
  location            = "Global"
  resource_group_name = azurerm_resource_group.service_health_rg.name
  scopes              = local.subscriptions_list
  description         = "Alert on Azure Service Health events across all incident types."

  criteria {
    category = "ServiceHealth"

    service_health {
      events = [
        "ActionRequired",
        "Informational",
        "Incident",
        "Maintenance",
        "Security"
      ]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.service_health_action_group.id
  }

  tags = local.common_tags
}
