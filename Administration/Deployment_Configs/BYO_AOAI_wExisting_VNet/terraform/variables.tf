variable "resource_group_name" {
  description = "Name of the resource group where the AI Foundry resources will be deployed."
  type        = string
}

variable "account_base_name" {
  description = "Base name for the AI Foundry account; a 4-character suffix is appended for uniqueness."
  type        = string
  default     = "foundry"

  validation {
    condition     = length(var.account_base_name) > 0 && length(var.account_base_name) <= 9
    error_message = "account_base_name must be between 1 and 9 characters to remain within Azure naming limits."
  }
}

variable "location" {
  description = "Azure region for the AI Foundry account and supporting resources."
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

variable "project_name" {
  description = "Optional project resource name. Leave blank to default to <account-name>-proj."
  type        = string
  default     = null
}

variable "project_display_name" {
  description = "Display name applied to the AI Foundry project."
  type        = string
  default     = "Project Display Name"
}

variable "project_description" {
  description = "Description stored on the AI Foundry project."
  type        = string
  default     = "Sample project provisioned by Terraform."
}

variable "existing_vnet_resource_id" {
  description = "Resource ID for the existing virtual network that hosts the private endpoint."
  type        = string
}

variable "existing_pe_subnet_resource_id" {
  description = "Resource ID for the existing subnet dedicated to private endpoints (network policies disabled)."
  type        = string
}

variable "existing_aoai_resource_id" {
  description = "Resource ID of the existing Azure OpenAI account that the project will connect to."
  type        = string
}
