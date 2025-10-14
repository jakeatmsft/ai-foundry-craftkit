resource "azapi_resource" "project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name      = local.project_name
  location  = local.account_location
  parent_id = var.existing_ai_foundry_account_resource_id

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

resource "azapi_resource" "azure_openai_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = local.azure_openai_connection_name
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category = "AzureOpenAI"
      target   = local.azure_openai_endpoint
      authType = "AAD"
      metadata = local.azure_openai_metadata
    }
  }

  depends_on = [time_sleep.after_project]

  lifecycle {
    precondition {
      condition     = local.azure_openai_endpoint != null && trimspace(local.azure_openai_endpoint) != ""
      error_message = "Resolved Azure OpenAI endpoint is empty; verify the azure_openai_resource_id input."
    }
  }
}

resource "azapi_resource" "azure_ai_search_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = local.azure_ai_search_connection_name
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category = "AzureAISearch"
      target   = local.azure_ai_search_endpoint
      authType = "AAD"
      metadata = local.azure_ai_search_metadata
    }
  }

  depends_on = [time_sleep.after_project]

  lifecycle {
    precondition {
      condition     = local.azure_ai_search_endpoint != null && trimspace(local.azure_ai_search_endpoint) != ""
      error_message = "Resolved Azure AI Search endpoint is empty; verify the azure_ai_search_resource_id input."
    }
  }
}

resource "azapi_resource" "cosmosdb_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = local.cosmosdb_connection_name
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category = "AzureCosmosDB"
      target   = local.cosmosdb_endpoint
      authType = "AAD"
      metadata = local.cosmosdb_metadata
    }
  }

  depends_on = [time_sleep.after_project]

  lifecycle {
    precondition {
      condition     = local.cosmosdb_endpoint != null && trimspace(local.cosmosdb_endpoint) != ""
      error_message = "Resolved Cosmos DB endpoint is empty; verify the cosmosdb_account_resource_id input."
    }
  }
}

resource "azapi_resource" "storage_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = local.storage_connection_name
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category = "AzureStorage"
      target   = local.storage_endpoint
      authType = "AAD"
      metadata = local.storage_metadata
    }
  }

  depends_on = [time_sleep.after_project]

  lifecycle {
    precondition {
      condition     = local.storage_endpoint != null && trimspace(local.storage_endpoint) != ""
      error_message = "Resolved storage endpoint is empty; verify storage_service and storage_account_resource_id inputs."
    }
  }
}

resource "time_sleep" "after_connections" {
  depends_on = [
    azapi_resource.azure_openai_connection,
    azapi_resource.azure_ai_search_connection,
    azapi_resource.cosmosdb_connection,
    azapi_resource.storage_connection
  ]
  create_duration = "30s"
}

resource "azapi_resource" "project_capability_host" {
  type      = "Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview"
  name      = local.project_capability_host_name
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      capabilityHostKind    = "Agents"
      aiServicesConnections = local.ai_services_connection_names
    }
  }

  depends_on = [
    time_sleep.after_connections
  ]

  lifecycle {
    precondition {
      condition     = length(local.ai_services_connection_names) > 0
      error_message = "At least one connection name must be provided for the capability host."
    }
  }
}
