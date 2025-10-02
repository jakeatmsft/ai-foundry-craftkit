output "account_id" {
  description = "Resource ID of the deployed AI Foundry account."
  value       = azapi_resource.account.id
}

output "account_name" {
  description = "Name of the AI Foundry account."
  value       = azapi_resource.account.name
}

output "account_endpoint" {
  description = "Endpoint URI for the AI Foundry account."
  value       = try(local.account_read.properties.endpoint, null)
}

output "project_name" {
  description = "Name of the AI Foundry project."
  value       = azapi_resource.project.name
}

output "project_connection_name" {
  description = "Resource ID of the BYO Azure OpenAI project connection."
  value       = azapi_resource.byo_aoai_connection.id
}
