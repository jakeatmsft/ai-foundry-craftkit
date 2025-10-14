locals {
  account_name     = data.azapi_resource.ai_foundry_account.name
  account_location = data.azapi_resource.ai_foundry_account.location
  project_name_input = coalesce(var.project_name, "")
  project_name       = trimspace(local.project_name_input) != "" ? trimspace(local.project_name_input) : "${local.account_name}-proj"

  project_capability_host_name_input = coalesce(var.project_capability_host_name, "")
  project_capability_host_name       = trimspace(local.project_capability_host_name_input) != "" ? trimspace(local.project_capability_host_name_input) : "${local.project_name}-capHost"

  azure_openai_output   = data.azapi_resource.azure_openai.output
  azure_openai_endpoint = try(local.azure_openai_output.properties.endpoint, null)
  azure_openai_location = data.azapi_resource.azure_openai.location

  azure_ai_search_output   = data.azapi_resource.azure_ai_search.output
  azure_ai_search_hostname = try(local.azure_ai_search_output.properties.hostName, null)
  azure_ai_search_endpoint = local.azure_ai_search_hostname != null && trimspace(local.azure_ai_search_hostname) != "" ? "https://${local.azure_ai_search_hostname}" : try(local.azure_ai_search_output.properties.endpoint, null)

  cosmosdb_output   = data.azapi_resource.cosmosdb_account.output
  cosmosdb_endpoint = try(local.cosmosdb_output.properties.documentEndpoint, null)

  storage_output             = data.azapi_resource.storage_account.output
  storage_primary_endpoints  = try(local.storage_output.properties.primaryEndpoints, {})
  storage_service_key        = lower(var.storage_service)
  storage_endpoint           = try(local.storage_primary_endpoints[local.storage_service_key], null)

  azure_openai_connection_name_input = trimspace(var.azure_openai_connection_name)
  azure_openai_connection_name       = local.azure_openai_connection_name_input != "" ? local.azure_openai_connection_name_input : "aoaiConnection"

  azure_ai_search_connection_name_input = trimspace(var.azure_ai_search_connection_name)
  azure_ai_search_connection_name       = local.azure_ai_search_connection_name_input != "" ? local.azure_ai_search_connection_name_input : "aiSearchConnection"

  cosmosdb_connection_name_input = trimspace(var.cosmosdb_connection_name)
  cosmosdb_connection_name       = local.cosmosdb_connection_name_input != "" ? local.cosmosdb_connection_name_input : "cosmosConnection"

  storage_connection_name_input = trimspace(var.storage_connection_name)
  storage_connection_name       = local.storage_connection_name_input != "" ? local.storage_connection_name_input : "storageConnection"

  azure_openai_metadata = merge(
    {
      ApiType    = "Azure"
      ResourceId = var.azure_openai_resource_id
      location   = local.azure_openai_location
    },
    var.azure_openai_additional_metadata
  )

  azure_ai_search_metadata = merge(
    {
      ResourceId = var.azure_ai_search_resource_id
      IndexName  = var.azure_ai_search_index_name
    },
    var.azure_ai_search_semantic_configuration_name != null && trimspace(var.azure_ai_search_semantic_configuration_name) != "" ? { SemanticConfiguration = trimspace(var.azure_ai_search_semantic_configuration_name) } : {},
    var.azure_ai_search_additional_metadata
  )

  cosmosdb_metadata = merge(
    {
      ResourceId     = var.cosmosdb_account_resource_id
      AccountName    = data.azapi_resource.cosmosdb_account.name
      DatabaseName   = var.cosmosdb_database_name
      ContainerName  = var.cosmosdb_container_name
      AccountEndpoint = local.cosmosdb_endpoint
    },
    var.cosmosdb_additional_metadata
  )

  storage_metadata = merge(
    {
      ResourceId         = var.storage_account_resource_id
      StorageAccountName = data.azapi_resource.storage_account.name
      ContainerName      = var.storage_container_name
      StorageService     = var.storage_service
    },
    var.storage_additional_metadata
  )

  ai_services_connection_names = [
    local.azure_openai_connection_name,
    local.azure_ai_search_connection_name,
    local.cosmosdb_connection_name,
    local.storage_connection_name
  ]
}
