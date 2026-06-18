output "account_id" {
  description = "Resource ID of the deployed AI Foundry account."
  value       = azapi_resource.ai_foundry.id
}

output "account_name" {
  description = "Name of the AI Foundry account."
  value       = azapi_resource.ai_foundry.name
}

output "account_endpoint" {
  description = "Endpoint URI for the AI Foundry account."
  value       = try(local.account_read.properties.endpoint, null)
}

output "managed_identity_principal_id" {
  description = "Principal ID of the system-assigned managed identity on the AI Foundry account."
  value       = try(local.account_read.identity.principalId, null)
}

output "model_deployment_id" {
  description = "Resource ID of the gpt-5-mini deployment when deploy_model is true."
  value       = var.deploy_model ? azapi_resource.model_deployment[0].id : null
}

output "model_deployment_name" {
  description = "Name of the gpt-5-mini deployment when deploy_model is true."
  value       = var.deploy_model ? azapi_resource.model_deployment[0].name : null
}
