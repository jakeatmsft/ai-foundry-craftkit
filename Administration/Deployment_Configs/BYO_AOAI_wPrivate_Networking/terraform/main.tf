resource "random_string" "account_suffix" {
  length  = 4
  upper   = false
  special = false

  keepers = {
    account_base_name = var.account_base_name
  }
}

resource "azapi_resource" "account" {
  type      = "Microsoft.CognitiveServices/accounts@2025-04-01-preview"
  name      = local.ai_foundry_name
  location  = var.location
  parent_id = data.azurerm_resource_group.target.id

  body = {
    identity = {
      type = "SystemAssigned"
    }
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    properties = {
      allowProjectManagement = true
      customSubDomainName    = local.ai_foundry_name
      disableLocalAuth       = false
      publicNetworkAccess    = "Disabled"
    }
  }
}

resource "time_sleep" "after_account" {
  depends_on      = [azapi_resource.account]
  create_duration = "30s"
}

resource "azurerm_virtual_network" "main" {
  name                = var.vnet_name
  location            = var.location
  resource_group_name = data.azurerm_resource_group.target.name
  address_space       = [var.vnet_address_prefix]
}

resource "azurerm_subnet" "private_endpoint" {
  name                 = var.pe_subnet_name
  resource_group_name  = data.azurerm_resource_group.target.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.pe_subnet_prefix]

  private_endpoint_network_policies_enabled = false
}

resource "azurerm_private_dns_zone" "ai_services" {
  name                = "privatelink.services.ai.azure.com"
  resource_group_name = data.azurerm_resource_group.target.name
}

resource "azurerm_private_dns_zone" "openai" {
  name                = "privatelink.openai.azure.com"
  resource_group_name = data.azurerm_resource_group.target.name
}

resource "azurerm_private_dns_zone" "cognitive_services" {
  name                = "privatelink.cognitiveservices.azure.com"
  resource_group_name = data.azurerm_resource_group.target.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "ai_services" {
  name                  = "aiServices-link"
  resource_group_name   = data.azurerm_resource_group.target.name
  private_dns_zone_name = azurerm_private_dns_zone.ai_services.name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
}

resource "azurerm_private_dns_zone_virtual_network_link" "openai" {
  name                  = "aiServicesOpenAI-link"
  resource_group_name   = data.azurerm_resource_group.target.name
  private_dns_zone_name = azurerm_private_dns_zone.openai.name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
}

resource "azurerm_private_dns_zone_virtual_network_link" "cognitive_services" {
  name                  = "aiServicesCognitiveServices-link"
  resource_group_name   = data.azurerm_resource_group.target.name
  private_dns_zone_name = azurerm_private_dns_zone.cognitive_services.name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
}

resource "azurerm_private_endpoint" "account" {
  name                = "${local.ai_foundry_name}-private-endpoint"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.target.name
  subnet_id           = azurerm_subnet.private_endpoint.id

  private_service_connection {
    name                           = "${local.ai_foundry_name}-private-link-service-connection"
    is_manual_connection           = false
    private_connection_resource_id = azapi_resource.account.id
    subresource_names              = ["account"]
  }

  private_dns_zone_group {
    name = "${local.ai_foundry_name}-dns-group"
    private_dns_zone_ids = [
      azurerm_private_dns_zone.ai_services.id,
      azurerm_private_dns_zone.openai.id,
      azurerm_private_dns_zone.cognitive_services.id
    ]
  }

  depends_on = [
    time_sleep.after_account,
    azurerm_private_dns_zone_virtual_network_link.ai_services,
    azurerm_private_dns_zone_virtual_network_link.openai,
    azurerm_private_dns_zone_virtual_network_link.cognitive_services
  ]
}

resource "azapi_resource" "project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name      = local.project_name
  location  = var.location
  parent_id = azapi_resource.account.id

  depends_on = [
    time_sleep.after_account
  ]

  body = {
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      description = var.project_description
      displayName = var.project_display_name
    }
  }
}

resource "time_sleep" "after_project" {
  depends_on      = [azapi_resource.project]
  create_duration = "30s"
}

resource "azapi_resource" "byo_aoai_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = local.byo_aoai_connection_name
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category = "AzureOpenAI"
      target   = local.existing_aoai.properties.endpoint
      authType = "AAD"
      metadata = {
        ApiType    = "Azure"
        ResourceId = var.existing_aoai_resource_id
        location   = local.existing_aoai_location
      }
    }
  }
}

resource "azapi_resource" "account_capability_host" {
  type      = "Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview"
  name      = local.account_capability_host
  parent_id = azapi_resource.account.id
  body = {
    properties = {
      capabilityHostKind = "Agents"
    }
  }
  depends_on = [
    azapi_resource.byo_aoai_connection,
    time_sleep.after_project
  ]
}

resource "time_sleep" "after_account_capability_host" {
  depends_on      = [azapi_resource.account_capability_host]
  create_duration = "30s"
}

resource "azapi_resource" "project_capability_host" {
  type      = "Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview"
  name      = local.project_capability_host
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      capabilityHostKind    = "Agents"
      aiServicesConnections = [local.byo_aoai_connection_name]
    }
  }

  depends_on = [
    azapi_resource.byo_aoai_connection,
    time_sleep.after_account_capability_host
  ]
}

resource "time_sleep" "after_project_capability_host" {
  depends_on      = [azapi_resource.project_capability_host]
  create_duration = "30s"
}
