output "project_id" {
  description = "Resource ID of the AI Foundry project."
  value       = azapi_resource.project.id
}

output "project_name" {
  description = "Name of the AI Foundry project."
  value       = azapi_resource.project.name
}

output "project_capability_host_id" {
  description = "Resource ID of the project capability host."
  value       = azapi_resource.project_capability_host.id
}

output "project_connection_ids" {
  description = "Map of connection names to resource IDs created for the project."
  value = zipmap(
    local.ai_services_connection_names,
    [
      azapi_resource.azure_openai_connection.id,
      azapi_resource.azure_ai_search_connection.id,
      azapi_resource.cosmosdb_connection.id,
      azapi_resource.storage_connection.id
    ]
  )
}
