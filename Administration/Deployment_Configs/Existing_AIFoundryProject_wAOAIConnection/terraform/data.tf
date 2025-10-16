data "azapi_resource" "ai_foundry_account" {
  type        = "Microsoft.CognitiveServices/accounts@2025-04-01-preview"
  resource_id = var.existing_ai_foundry_account_resource_id
}

data "azapi_resource" "azure_openai" {
  type        = "Microsoft.CognitiveServices/accounts@2023-05-01"
  resource_id = var.azure_openai_resource_id
}
