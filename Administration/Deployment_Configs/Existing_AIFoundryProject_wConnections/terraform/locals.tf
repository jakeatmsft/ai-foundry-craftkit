locals {
  account_name     = data.azapi_resource.ai_foundry_account.name
  account_location = data.azapi_resource.ai_foundry_account.location

  project_name_input = coalesce(var.project_name, "")
  project_name       = trimspace(local.project_name_input) != "" ? trimspace(local.project_name_input) : "${local.account_name}-proj"

  project_capability_host_name_input = coalesce(var.project_capability_host_name, "")
  project_capability_host_name       = trimspace(local.project_capability_host_name_input) != "" ? trimspace(local.project_capability_host_name_input) : "${local.project_name}-capHost"

  azure_openai_output   = data.azapi_resource.azure_openai.output
  azure_openai_name     = coalesce(try(local.azure_openai_output.name, null), try(data.azapi_resource.azure_openai.name, null), regex("[^/]+$", var.azure_openai_resource_id))
  azure_openai_endpoint = try(local.azure_openai_output.properties.endpoint, null)
  azure_openai_location = data.azapi_resource.azure_openai.location

  azure_ai_search_output   = data.azapi_resource.azure_ai_search.output
  azure_ai_search_name     = coalesce(try(local.azure_ai_search_output.name, null), try(data.azapi_resource.azure_ai_search.name, null), regex("[^/]+$", var.azure_ai_search_resource_id))
  azure_ai_search_hostname = try(local.azure_ai_search_output.properties.hostName, null)
  azure_ai_search_endpoint = local.azure_ai_search_hostname != null && trimspace(local.azure_ai_search_hostname) != "" ? format("https://%s", local.azure_ai_search_hostname) : format("https://%s.search.windows.net", local.azure_ai_search_name)
  azure_ai_search_location = data.azapi_resource.azure_ai_search.location

  cosmosdb_output   = data.azapi_resource.cosmosdb_account.output
  cosmosdb_name     = coalesce(try(local.cosmosdb_output.name, null), try(data.azapi_resource.cosmosdb_account.name, null), regex("[^/]+$", var.cosmosdb_account_resource_id))
  cosmosdb_endpoint = try(local.cosmosdb_output.properties.documentEndpoint, null)
  cosmosdb_location = data.azapi_resource.cosmosdb_account.location

  storage_output            = data.azapi_resource.storage_account.output
  storage_name              = coalesce(try(local.storage_output.name, null), try(data.azapi_resource.storage_account.name, null), regex("[^/]+$", var.storage_account_resource_id))
  storage_primary_endpoints = try(local.storage_output.properties.primaryEndpoints, {})
  storage_blob_endpoint     = try(local.storage_primary_endpoints.blob, null)
  storage_location          = data.azapi_resource.storage_account.location

  azure_openai_metadata = {
    ApiType    = "Azure"
    ResourceId = var.azure_openai_resource_id
    location   = local.azure_openai_location
  }

  azure_ai_search_metadata = {
    ApiType    = "Azure"
    ApiVersion = "2025-05-01-preview"
    ResourceId = var.azure_ai_search_resource_id
    location   = local.azure_ai_search_location
  }

  cosmosdb_metadata = {
    ApiType    = "Azure"
    ResourceId = var.cosmosdb_account_resource_id
    location   = local.cosmosdb_location
  }

  storage_metadata = {
    ApiType    = "Azure"
    ResourceId = var.storage_account_resource_id
    location   = local.storage_location
  }

  ai_services_connection_names = [
    local.azure_openai_name,
    local.azure_ai_search_name,
    local.cosmosdb_name,
    local.storage_name
  ]
}
