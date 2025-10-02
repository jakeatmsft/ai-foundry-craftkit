variable "resource_group_name" {
  type        = string
  description = "Name of the resource group where all resources will be deployed."
}

variable "account_base_name" {
  type        = string
  description = "Base name for the AI Foundry account; a 4-character suffix is appended for uniqueness."
  default     = "foundry"

  validation {
    condition     = length(var.account_base_name) > 0 && length(var.account_base_name) <= 9
    error_message = "account_base_name must be between 1 and 9 characters to remain within Azure naming limits."
  }
}

variable "location" {
  type        = string
  description = "Azure region where the AI Foundry account and networking resources will be created."
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
  default     = "Sample project provisioned by Terraform."
}

variable "vnet_name" {
  type        = string
  description = "Name of the virtual network that will host the AI Foundry private endpoint."
  default     = "private-vnet"
}

variable "pe_subnet_name" {
  type        = string
  description = "Name of the subnet dedicated to private endpoints within the virtual network."
  default     = "pe-subnet"
}

variable "vnet_address_prefix" {
  type        = string
  description = "CIDR address prefix for the virtual network."
  default     = "192.168.0.0/16"
}

variable "pe_subnet_prefix" {
  type        = string
  description = "CIDR address prefix for the private endpoint subnet."
  default     = "192.168.0.0/24"
}

variable "existing_aoai_resource_id" {
  type        = string
  description = "Resource ID of the existing Azure OpenAI account that the project will connect to."
}
