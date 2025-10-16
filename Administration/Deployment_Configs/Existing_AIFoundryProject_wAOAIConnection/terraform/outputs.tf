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

output "project_connection_id" {
  description = "Resource ID of the Azure OpenAI project connection."
  value       = azapi_resource.azure_openai_connection.id
}
