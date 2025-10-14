variable "existing_ai_foundry_account_resource_id" {
  description = "Resource ID of the existing AI Foundry account that will host the project."
  type        = string
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

variable "azure_openai_resource_id" {
  description = "Resource ID of the existing Azure OpenAI account that the project will connect to."
  type        = string
}

variable "azure_ai_search_resource_id" {
  description = "Resource ID of the existing Azure AI Search service that the project will connect to."
  type        = string
}

variable "cosmosdb_account_resource_id" {
  description = "Resource ID of the existing Azure Cosmos DB account that the project will connect to."
  type        = string
}

variable "storage_account_resource_id" {
  description = "Resource ID of the existing Azure Storage account that the project will connect to."
  type        = string
}

variable "project_capability_host_name" {
  description = "Optional name for the project capability host. Leave blank to default to <project-name>-capHost."
  type        = string
  default     = null
}
