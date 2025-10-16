variable "resource_group_name" {
  description = "Name of the resource group where all resources will be deployed."
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
  description = "Azure region where the AI Foundry account and networking resources will be created."
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

variable "vnet_name" {
  description = "Name of the virtual network that will host the AI Foundry private endpoint."
  type        = string
  default     = "private-vnet"
}

variable "pe_subnet_name" {
  description = "Name of the subnet dedicated to private endpoints within the virtual network."
  type        = string
  default     = "pe-subnet"
}

variable "vnet_address_prefix" {
  description = "CIDR address prefix for the virtual network."
  type        = string
  default     = "192.168.0.0/16"
}

variable "pe_subnet_prefix" {
  description = "CIDR address prefix for the private endpoint subnet."
  type        = string
  default     = "192.168.0.0/24"
}

variable "agent_subnet_name" {
  description = "Name of the subnet dedicated to AI Foundry agent workloads within the virtual network."
  type        = string
  default     = "agent-subnet"
}

variable "agent_subnet_prefix" {
  description = "CIDR address prefix for the agent subnet that will be injected into the AI Foundry account."
  type        = string
  default     = "192.168.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.agent_subnet_prefix))
    error_message = "agent_subnet_prefix must be a valid CIDR block."
  }
}

variable "existing_aoai_resource_id" {
  description = "Resource ID of the existing Azure OpenAI account that the project will connect to."
  type        = string
}

variable "existing_aoai_resource_location" {
  description = "Resource location of the existing Azure OpenAI account that the project will connect to."
  type        = string
}
