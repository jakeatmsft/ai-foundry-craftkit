data "azurerm_resource_group" "target" {
  name = var.resource_group_name
}

data "azapi_resource" "account_read" {
  type        = "Microsoft.CognitiveServices/accounts@2025-06-01"
  resource_id = azapi_resource.ai_foundry.id
  depends_on  = [time_sleep.after_account]
}
