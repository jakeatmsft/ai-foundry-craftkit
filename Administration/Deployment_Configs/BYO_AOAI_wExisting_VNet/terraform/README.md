# AI Foundry BYO Azure OpenAI (Terraform)

This Terraform configuration deploys an AI Foundry account that connects to an existing Azure OpenAI resource while linking the account to an existing virtual network through a private endpoint. Use it when you want to manage AI Foundry resources in a centrally managed VNet but rely on a pre-provisioned Azure OpenAI account.

## Prerequisites

- Terraform 1.6.0 or later.
- Azure CLI logged in to the target subscription (`az login`) or another supported azurerm authentication method.
- An Azure resource group in the target subscription where the AI Foundry resources will be created.
- A virtual network and subnet dedicated to private endpoints with network policies disabled.
- An existing Azure OpenAI account whose resource ID you can reference.

## Configuration

Copy `terraform.tfvars.example` to `terraform.tfvars` (or another `-var-file`) and update the values:

- `resource_group_name`: Resource group hosting every deployed resource.
- `account_base_name`: Base string used to generate the AI Foundry account name; a 4 character suffix is appended automatically.
- `location`: Azure region for the deployment. Must be one of the regions permitted in `variables.tf`.
- `project_name`: Optional project resource name; defaults to `<account-name>-proj` when omitted.
- `project_display_name`, `project_description`: Metadata stored with the project.
- `existing_vnet_resource_id`: Resource ID of the virtual network that will be linked to the private DNS zones.
- `existing_pe_subnet_resource_id`: Resource ID of the subnet that will host the private endpoint.
- `existing_aoai_resource_id`: Resource ID of the Azure OpenAI account that will back the AI Foundry project connection.

## Deploy

```bash
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

The deployment creates:

- An AI Foundry account (`AIServices`) with a system-assigned managed identity and public network access disabled.
- Private DNS zones for AI Foundry, OpenAI, and Cognitive Services linked to the existing VNet.
- A private endpoint bound to the existing subnet.
- An AI Foundry project with a managed identity and a BYO Azure OpenAI connection wired to the existing account.

## Outputs

After `terraform apply`, the following values are returned:

- `account_id`: Resource ID of the AI Foundry account.
- `account_name`: Name of the AI Foundry account.
- `account_endpoint`: Public endpoint for the AI Foundry account.
- `project_name`: Name of the project resource.
- `project_connection_name`: Resource ID of the BYO Azure OpenAI project connection.

## Cleanup

Run `terraform destroy -var-file="terraform.tfvars"` to remove all resources created by this configuration. The referenced VNet, subnet, and Azure OpenAI account are not modified.
