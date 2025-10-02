locals {
  ai_foundry_name          = "${var.account_base_name}${random_string.account_suffix.result}"
  project_name             = var.project_name != null && var.project_name != "" ? var.project_name : "${local.ai_foundry_name}-proj"
  byo_aoai_connection_name = "aoaiConnection"
  account_capability_host  = "${local.ai_foundry_name}-capHost"
  project_capability_host  = "${local.project_name}-capHost"
  account_read             = data.azapi_resource.account_read.output
  existing_aoai            = data.azapi_resource.existing_aoai.output
  existing_aoai_location   = data.azapi_resource.existing_aoai.location
  
}
