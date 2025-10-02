data "azurerm_resource_group" "target" {
  name = var.resource_group_name
}

data "azapi_resource" "existing_aoai" {
  type        = "Microsoft.CognitiveServices/accounts@2023-05-01"
  resource_id = var.existing_aoai_resource_id
}

data "azapi_resource" "account_read" {
  type        = "Microsoft.CognitiveServices/accounts@2025-04-01-preview"
  resource_id = azapi_resource.account.id
}

