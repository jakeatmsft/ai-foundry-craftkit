# AI Foundry BYO Azure OpenAI with Private Networking (Terraform)

This Terraform configuration mirrors the Bicep template in `../bicep` by deploying an Azure AI Foundry account locked to private networking and wiring it to an existing Azure OpenAI account. It stands up the networking infrastructure required for Private Link, then provisions the AI Foundry project, connection, and capability hosts that bind to the BYO Azure OpenAI resource.

## Prerequisites

- Terraform 1.6.0 or later.
- Azure CLI logged in to the target subscription (`az login`) or another supported azurerm authentication method.
- Permissions to create virtual networks, private endpoints, and Cognitive Services resources in the destination subscription.
- The resource ID for an existing Azure OpenAI account you wish to connect (for example `"/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<name>"`).

## Configuration

Copy `terraform.tfvars.example` to `terraform.tfvars` (or another `-var-file`) and adjust the inputs:

- `resource_group_name`: Resource group that will hold every created resource.
- `account_base_name`: Base string used to derive the AI Foundry account name; a 4-character suffix is appended automatically.
- `location`: Azure region for all resources. Must be one of the supported regions listed in `variables.tf`.
- `project_name`: Optional project resource name. Defaults to `<account-name>-proj` when omitted.
- `project_display_name`, `project_description`: Project metadata values.
- `vnet_name`, `pe_subnet_name`: Names assigned to the new virtual network and private endpoint subnet.
- `vnet_address_prefix`, `pe_subnet_prefix`: CIDR prefixes used for the virtual network and subnet.
- `existing_aoai_resource_id`: Resource ID of the Azure OpenAI account that will back the BYO connection.

Ensure the CIDR ranges you specify do not overlap with existing networks that will peer with or route to this virtual network.

## Deploy

```bash
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

Resources created by this configuration include:

- An AI Foundry account (`AIServices`) with a system-assigned managed identity and public network access disabled.
- A virtual network and dedicated private endpoint subnet with network policies disabled.
- Private DNS zones for AI Foundry, OpenAI, and Cognitive Services plus links to the new virtual network.
- A private endpoint mapped to the AI Foundry account and associated DNS zone group.
- An AI Foundry project with a managed identity, BYO Azure OpenAI connection, and matching capability hosts at the account and project scopes.

## Outputs

After `terraform apply`, Terraform emits:

- `account_id`: Resource ID of the AI Foundry account.
- `account_name`: Name of the AI Foundry account.
- `account_endpoint`: Endpoint URI for the account (accessible via private connectivity).
- `project_name`: Name of the AI Foundry project resource.
- `project_connection_name`: Resource ID of the BYO Azure OpenAI project connection.

## Cleanup

Run `terraform destroy -var-file="terraform.tfvars"` when you need to remove the provisioned infrastructure. The existing Azure OpenAI account referenced by `existing_aoai_resource_id` is left untouched.
