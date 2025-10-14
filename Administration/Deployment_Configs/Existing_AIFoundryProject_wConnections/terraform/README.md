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

The module derives connection metadata directly from the referenced Azure resources, so only the resource IDs are required.

## Key input variables

| Variable | Description |
|----------|-------------|
| `existing_ai_foundry_account_resource_id` | Resource ID of the existing AI Foundry account that will host the project. |
| `azure_openai_resource_id` | Resource ID of the Azure OpenAI account that will be referenced by the project connection. |
| `azure_ai_search_resource_id` | Resource ID of the Azure AI Search service to connect. |
| `cosmosdb_account_resource_id` | Resource ID of the Cosmos DB account to connect. |
| `storage_account_resource_id` | Resource ID of the Storage account to connect. |
| `project_name` | Optional project resource name (defaults to `<account-name>-proj`). |
| `project_display_name` / `project_description` | Optional display metadata applied to the project. |
| `project_capability_host_name` | Optional override for the capability host name (defaults to `<project-name>-capHost`). |

Refer to `variables.tf` for the complete list of optional overrides (project naming only).

## Outputs

- `project_id` – Resource ID of the project.
- `project_name` – Name of the project.
- `project_capability_host_id` – Resource ID of the project capability host.
- `project_connection_ids` – Map of connection names to the created connection resource IDs.
