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

  azure_openai_metadata = {
    ApiType    = "Azure"
    ResourceId = var.azure_openai_resource_id
    location   = local.azure_openai_location
  }

  ai_services_connection_names = [local.azure_openai_name]
}
