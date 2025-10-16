# Existing AI Foundry Project With Azure OpenAI Connection (Terraform)

This configuration adds a new Azure AI Foundry project to an **existing** account, connects the project to an existing Azure OpenAI resource, and provisions a project-level capability host for Agents workloads.

## What gets created

- AI Foundry project with managed identity enabled.
- Single project connection targeting an existing Azure OpenAI account.
- Project capability host configured for the Agents capability and bound to the Azure OpenAI connection.

## Prerequisites

- Terraform 1.6.0 or later.
- Azure CLI (logged in) or environment variables that allow the Terraform AzureRM provider to authenticate.
- Existing Azure AI Foundry account.
- Existing Azure OpenAI resource in a supported region.
- Permissions to read the existing resources and create AI Foundry child resources (project, connection, capability host).

## Usage

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and update the values with your environment specifics.
2. Run `terraform init`.
3. Run `terraform plan` to validate the configuration.
4. Run `terraform apply` to create the project, connection, and capability host.

The module derives connection metadata directly from the referenced Azure resources, so only the resource IDs are required.

## Key input variables

| Variable | Description |
|----------|-------------|
| `existing_ai_foundry_account_resource_id` | Resource ID of the existing AI Foundry account that will host the project. |
| `azure_openai_resource_id` | Resource ID of the Azure OpenAI account to connect. |
| `project_name` | Optional project resource name (defaults to `<account-name>-proj`). |
| `project_display_name` / `project_description` | Optional display metadata applied to the project. |
| `project_capability_host_name` | Optional override for the capability host name (defaults to `<project-name>-capHost`). |

## Outputs

- `project_id` – Resource ID of the project.
- `project_name` – Name of the project.
- `project_capability_host_id` – Resource ID of the project capability host.
- `project_connection_id` – Resource ID of the Azure OpenAI project connection.
