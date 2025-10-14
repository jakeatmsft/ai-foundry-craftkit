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

variable "azure_openai_connection_name" {
  description = "Name assigned to the Azure OpenAI project connection."
  type        = string
  default     = "aoaiConnection"
}

variable "azure_openai_additional_metadata" {
  description = "Optional key/value pairs appended to the Azure OpenAI connection metadata payload."
  type        = map(string)
  default     = {}
}

variable "azure_ai_search_resource_id" {
  description = "Resource ID of the existing Azure AI Search service that the project will connect to."
  type        = string
}

variable "azure_ai_search_index_name" {
  description = "Name of the Azure AI Search index exposed to the project connection."
  type        = string
}

variable "azure_ai_search_semantic_configuration_name" {
  description = "Optional semantic configuration name to associate with the Azure AI Search connection."
  type        = string
  default     = null
}

variable "azure_ai_search_connection_name" {
  description = "Name assigned to the Azure AI Search project connection."
  type        = string
  default     = "aiSearchConnection"
}

variable "azure_ai_search_additional_metadata" {
  description = "Optional key/value pairs appended to the Azure AI Search connection metadata payload."
  type        = map(string)
  default     = {}
}

variable "cosmosdb_account_resource_id" {
  description = "Resource ID of the existing Azure Cosmos DB account that the project will connect to."
  type        = string
}

variable "cosmosdb_database_name" {
  description = "Name of the Cosmos DB database exposed to the project connection."
  type        = string
}

variable "cosmosdb_container_name" {
  description = "Name of the Cosmos DB container exposed to the project connection."
  type        = string
}

variable "cosmosdb_connection_name" {
  description = "Name assigned to the Cosmos DB project connection."
  type        = string
  default     = "cosmosConnection"
}

variable "cosmosdb_additional_metadata" {
  description = "Optional key/value pairs appended to the Cosmos DB connection metadata payload."
  type        = map(string)
  default     = {}
}

variable "storage_account_resource_id" {
  description = "Resource ID of the existing Azure Storage account that the project will connect to."
  type        = string
}

variable "storage_container_name" {
  description = "Name of the Azure Storage container exposed to the project connection."
  type        = string
}

variable "storage_service" {
  description = "Storage service surface to expose through the connection (Blob, Queue, Table, or File)."
  type        = string
  default     = "Blob"

  validation {
    condition     = contains(["blob", "queue", "table", "file"], lower(var.storage_service))
    error_message = "storage_service must be one of: Blob, Queue, Table, File."
  }
}

variable "storage_connection_name" {
  description = "Name assigned to the Azure Storage project connection."
  type        = string
  default     = "storageConnection"
}

variable "storage_additional_metadata" {
  description = "Optional key/value pairs appended to the Azure Storage connection metadata payload."
  type        = map(string)
  default     = {}
}

variable "project_capability_host_name" {
  description = "Optional name for the project capability host. Leave blank to default to <project-name>-capHost."
  type        = string
  default     = null
}
