locals {
  ai_foundry_name                 = "${var.account_base_name}${random_string.account_suffix.result}"
  custom_subdomain_name_input     = coalesce(var.custom_subdomain_name, "")
  effective_custom_subdomain_name = trimspace(local.custom_subdomain_name_input) != "" ? trimspace(local.custom_subdomain_name_input) : local.ai_foundry_name
  account_read                    = data.azapi_resource.account_read.output
  model_name                      = "gpt-5-mini"
}
