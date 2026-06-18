variable "resource_group_name" {
  description = "Name of the resource group where the AI Foundry account will be deployed."
  type        = string
}

variable "account_base_name" {
  description = "Base name for the AI Foundry account; a 4-character suffix is appended for uniqueness."
  type        = string
  default     = "foundry"

  validation {
    condition     = length(var.account_base_name) > 0 && length(var.account_base_name) <= 9
    error_message = "account_base_name must be between 1 and 9 characters to remain within the naming pattern used by these templates."
  }
}

variable "location" {
  description = "Azure region for the AI Foundry account."
  type        = string
  default     = "eastus"

  validation {
    condition = contains([
      "australiaeast",
      "canadaeast",
      "eastus",
      "eastus2",
      "francecentral",
      "japaneast",
      "koreacentral",
      "norwayeast",
      "polandcentral",
      "southindia",
      "swedencentral",
      "switzerlandnorth",
      "uaenorth",
      "uksouth",
      "westus",
      "westus3",
      "westeurope",
      "southeastasia"
    ], lower(var.location))
    error_message = "location must be one of the supported AI Foundry regions."
  }
}

variable "public_network_access" {
  description = "Controls whether the AI Foundry account is reachable over the public internet."
  type        = string
  default     = "Enabled"

  validation {
    condition     = contains(["Enabled", "Disabled"], var.public_network_access)
    error_message = "public_network_access must be either Enabled or Disabled."
  }
}

variable "disable_local_auth" {
  description = "Controls whether API keys and other local auth methods are disabled on the AI Foundry account."
  type        = bool
  default     = false
}

variable "allow_project_management" {
  description = "Controls whether projects can be created under this AI Foundry account later."
  type        = bool
  default     = true
}

variable "custom_subdomain_name" {
  description = "Optional custom subdomain name. Leave null or empty to reuse the generated account name."
  type        = string
  default     = null
}

variable "deploy_model" {
  description = "Controls whether a default gpt-5-mini deployment is created in the AI Foundry account."
  type        = bool
  default     = true
}

variable "model_deployment_name" {
  description = "Name of the AI Foundry model deployment resource."
  type        = string
  default     = "gpt-5-mini"

  validation {
    condition     = trimspace(var.model_deployment_name) != ""
    error_message = "model_deployment_name must not be empty."
  }
}

variable "model_version" {
  description = "Version of the gpt-5-mini model to deploy."
  type        = string
  default     = "2025-08-07"
}

variable "model_sku_name" {
  description = "SKU name for the model deployment (for example, GlobalStandard or Standard)."
  type        = string
  default     = "GlobalStandard"
}

variable "model_capacity" {
  description = "Capacity assigned to the model deployment."
  type        = number
  default     = 10

  validation {
    condition     = var.model_capacity > 0
    error_message = "model_capacity must be greater than 0."
  }
}
