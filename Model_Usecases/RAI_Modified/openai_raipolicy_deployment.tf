locals {
  content_filter_template                     = file("${path.module}/openai_raipolicy_deployment.json")
  content_filter_template_awm                 = file("${path.module}/openai_raipolicy_deployment_awm.json")
  custom_content_filter_template              = file("${path.module}/openai_customraipolicy_deployment.json")
  custom_content_filter_template_ccb_async    = file("${path.module}/openai_raipolicy_deployment_ccb_async.json")
  custom_content_filter_template_ccb_nofilter = file("${path.module}/openai_raipolicy_deployment_ccb_nofilter.json")
}

resource "azapi_resource" "custom_content_filter" {
  type                      = "Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01"
  name                      = "JPMC-LLM-ContentFilter"
  parent_id                 = azurerm_cognitive_account.openai_service.id
  schema_validation_enabled = false
  body = {
    properties = jsondecode(local.content_filter_template)
  }
}

resource "azapi_resource" "custom_content_filter_awm" {
  count                     = var.general_index == "ae" || var.general_index == "aw" ? 1 : 0 # only create for AWM EXP and SRV
  type                      = "Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01"
  name                      = "JPMC-LLM-ContentFilter-AWM"
  parent_id                 = azurerm_cognitive_account.openai_service.id
  schema_validation_enabled = false
  body = {
    properties = jsondecode(local.content_filter_template_awm)
  }
}
resource "azapi_resource" "custom_content_filter_ccb_async" {
  #count     = (var.general_index == "ce" || var.general_index == "cc") && var.content_filter_policy == "custom" ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01"
  name                      = "CCB-LLM-ContentFilter-SCPD-ASYNC"
  parent_id                 = azurerm_cognitive_account.openai_service.id
  schema_validation_enabled = false
  body = {
    properties = jsondecode(local.custom_content_filter_template_ccb_async)
  }
}

# NOTE: This resource requires the Microsoft RAI modified-content-filter exception for
# the subscription. Azure rejects it without that exception because it disables the
# filters inherited from Microsoft.Default.
resource "azapi_resource" "custom_content_filter_ocas_nofilter" {
  #count     = (var.general_index == "ce" || var.general_index == "cc") && var.content_filter_policy == "custom" ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01"
  name                      = "CCB-LLM-ContentFilter-OCAS-NOFILTER"
  parent_id                 = azurerm_cognitive_account.openai_service.id
  schema_validation_enabled = false
  body = {
    properties = jsondecode(local.custom_content_filter_template_ccb_nofilter)
  }
}

/*
resource "azapi_resource" "custom_rai_policy" {
    count     = (var.general_index == "ct" || var.general_index == "cs") && var.content_filter_policy == "custom" ? 1 : 0
    type      = "Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01"
    name      = "JPMC-LLM-LowRestrictFilter"
    parent_id = azurerm_cognitive_account.openai_service.id
    schema_validation_enabled = false
    body = {
        properties = jsondecode(local.custom_content_filter_template)
    }
}
 */
