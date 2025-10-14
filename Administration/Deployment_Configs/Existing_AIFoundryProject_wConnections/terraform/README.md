# Existing AI Foundry Project With Connections (Terraform)

This configuration adds a new Azure AI Foundry project to an **existing** account, wires the project to existing Azure OpenAI, Azure AI Search, Azure Cosmos DB, and Azure Storage resources, and then provisions a project-level capability host for Agents workloads.

## What gets created

- AI Foundry project with managed identity enabled.
- Four project connections (Azure OpenAI, Azure AI Search, Azure Cosmos DB, Azure Storage) that reuse Bring Your Own (BYO) resources.
- Project capability host configured for the Agents capability and associated with the connection names.

## Prerequisites

- Terraform 1.6.0 or later.
- Azure CLI (logged in) or environment variables that allow the Terraform AzureRM provider to authenticate.
- Existing Azure AI Foundry account.
- Existing Azure OpenAI, Azure AI Search, Azure Cosmos DB (SQL API), and Azure Storage (Blob/Queue/Table/File) resources.
- The identities executing Terraform must have permissions to read the existing resources and to create AI Foundry child resources (project, connections, capability host).

## Usage

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and update the values with your environment specifics.
2. Run `terraform init`.
3. Run `terraform plan` to validate the configuration.
4. Run `terraform apply` to create the project, connections, and capability host.

> **Note:** Some connection metadata fields (for example, Cosmos DB consistency configuration or Azure Storage container-level options) may vary between environments. Optional `*_additional_metadata` variables are exposed to let you append extra key/value pairs required by your scenario.

## Key input variables

| Variable | Description |
|----------|-------------|
| `existing_ai_foundry_account_resource_id` | Resource ID of the existing AI Foundry account that will host the project. |
| `azure_openai_resource_id` | Resource ID of the Azure OpenAI account that will be referenced by the project connection. |
| `azure_ai_search_resource_id` | Resource ID of the Azure AI Search service to connect. |
| `azure_ai_search_index_name` | Azure AI Search index to expose. |
| `cosmosdb_account_resource_id` | Resource ID of the Cosmos DB account to connect. |
| `cosmosdb_database_name` / `cosmosdb_container_name` | Cosmos DB database and container names surfaced through the connection. |
| `storage_account_resource_id` | Resource ID of the Storage account to connect. |
| `storage_container_name` | Name of the container (or queue/table/file share) exposed via the storage connection. |
| `storage_service` | Storage service type (`Blob`, `Queue`, `Table`, or `File`). |

Refer to `variables.tf` for the complete list of optional overrides (connection names, semantic configuration, metadata extensions, etc.).

## Outputs

- `project_id` – Resource ID of the project.
- `project_name` – Name of the project.
- `project_capability_host_id` – Resource ID of the project capability host.
- `project_connection_ids` – Map of connection names to the created connection resource IDs.
