variable "resource_group_name" {
  type        = string
  description = "Name of the resource group where the AI Foundry resources will be deployed."
}

variable "account_base_name" {
  type        = string
  description = "Base name for the AI Foundry account; a 4-character suffix is appended for uniqueness."
  default     = "foundry"

  validation {
    condition     = length(var.account_base_name) <= 9 && length(var.account_base_name) > 0
    error_message = "account_base_name must be between 1 and 9 characters to remain within Azure naming limits."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the AI Foundry account and supporting resources."
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
  type        = string
  description = "Optional project resource name. Leave blank to default to <account-name>-proj."
  default     = null
}

variable "project_display_name" {
  type        = string
  description = "Display name applied to the AI Foundry project."
  default     = "Project Display Name"
}

variable "project_description" {
  type        = string
  description = "Description stored on the AI Foundry project."
  default     = "Sample project provisioned by Bicep."
}

variable "existing_vnet_resource_id" {
  type        = string
  description = "Resource ID for the existing virtual network that will host the private endpoint."
}

variable "existing_pe_subnet_resource_id" {
  type        = string
  description = "Resource ID for the existing subnet dedicated to private endpoints."
}

variable "existing_aoai_resource_id" {
  type        = string
  description = "Resource ID of the existing Azure OpenAI account that the project will connect to."
}
