resource "random_string" "account_suffix" {
  length  = 4
  upper   = false
  special = false

  keepers = {
    account_base_name = var.account_base_name
  }
}

resource "azapi_resource" "ai_foundry" {
  type                      = "Microsoft.CognitiveServices/accounts@2025-06-01"
  name                      = local.ai_foundry_name
  location                  = var.location
  parent_id                 = data.azurerm_resource_group.target.id
  schema_validation_enabled = false

  body = {
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      allowProjectManagement = var.allow_project_management
      customSubDomainName    = local.effective_custom_subdomain_name
      disableLocalAuth       = var.disable_local_auth
      publicNetworkAccess    = var.public_network_access
    }
  }
}

resource "time_sleep" "after_account" {
  depends_on      = [azapi_resource.ai_foundry]
  create_duration = "30s"
}

resource "azapi_resource" "model_deployment" {
  count                     = var.deploy_model ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/deployments@2024-10-01"
  name                      = var.model_deployment_name
  parent_id                 = azapi_resource.ai_foundry.id
  schema_validation_enabled = false

  body = {
    sku = {
      name     = var.model_sku_name
      capacity = var.model_capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = local.model_name
        version = var.model_version
      }
    }
  }

  depends_on = [time_sleep.after_account]
}
