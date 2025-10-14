data "azapi_resource" "ai_foundry_account" {
  type        = "Microsoft.CognitiveServices/accounts@2025-04-01-preview"
  resource_id = var.existing_ai_foundry_account_resource_id
}

data "azapi_resource" "azure_openai" {
  type        = "Microsoft.CognitiveServices/accounts@2023-05-01"
  resource_id = var.azure_openai_resource_id
}

data "azapi_resource" "azure_ai_search" {
  type        = "Microsoft.Search/searchServices@2023-11-01"
  resource_id = var.azure_ai_search_resource_id
}

data "azapi_resource" "cosmosdb_account" {
  type        = "Microsoft.DocumentDB/databaseAccounts@2024-05-15"
  resource_id = var.cosmosdb_account_resource_id
}

data "azapi_resource" "storage_account" {
  type        = "Microsoft.Storage/storageAccounts@2023-01-01"
  resource_id = var.storage_account_resource_id
}
