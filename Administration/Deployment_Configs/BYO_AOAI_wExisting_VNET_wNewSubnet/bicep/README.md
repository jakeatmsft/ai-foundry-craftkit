# BYO Azure OpenAI AI Foundry Deployment (Existing VNet, New Subnet)

This directory contains a Bicep template (`main.bicep`) as well as an equivalent Terraform configuration (`terraform/`) that deploys an Azure AI Foundry account with private networking while reusing an existing virtual network and creating dedicated subnets for the private endpoint and agent network injection. The deployment links the account to an existing Azure OpenAI resource through a project connection and configures capability hosts so the project can use that connection.

## What the template deploys
- **AI Foundry account** (`Microsoft.CognitiveServices/accounts`) with `AIServices` kind, system-assigned identity, and public network access disabled.
- **Private endpoint** to the AI Foundry account plus private DNS zones (`privatelink.services.ai.azure.com`, `privatelink.openai.azure.com`, `privatelink.cognitiveservices.azure.com`) linked to your existing VNet.
- **Agent subnet** provisioned in the existing VNet and wired through AI Foundry network injection for Standard Agents.
- **Project** inside the Foundry account with a BYO Azure OpenAI connection (`connections@2025-04-01-preview`).
- **Capability hosts** at both account and project scope so the project can use the BYO connection.
- **Sample model deployment** (`gpt-4o-mini`) inside the AI Foundry account for validation.

## Required inputs
Collect the following resource IDs:
- Existing virtual network: `/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Network/virtualNetworks/<vnet>`
- Existing Azure OpenAI account: `/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<aoai>`

Choose subnet names and address prefixes that will be created inside the VNet for the private endpoint and agent workloads. Ensure the prefixes fit within the VNet address space and do not overlap existing subnets.

## Deploy
1. Create or select a resource group in a supported region:
   ```bash
   az group create --name <rg-name> --location <region>
   ```
2. Deploy the template, providing the resource ID for the VNet along with the new subnet details and AOAI resource ID. You can edit `main.parameters.json` or pass values inline:
   ```bash
   az deployment group create \
     --resource-group <rg-name> \
     --template-file main.bicep \
     --parameters \
       existingVnetResourceId="/subscriptions/<...>/virtualNetworks/<...>" \
       newPeSubnetName="foundry-pe-subnet" \
       newPeSubnetPrefix="192.168.10.0/24" \
       newAgentSubnetName="foundry-agent-subnet" \
       newAgentSubnetPrefix="192.168.11.0/24" \
       existingAoaiResourceId="/subscriptions/<...>/accounts/<...>"
   ```

## Terraform
The Terraform project under `terraform/` provisions the same resources using the `azurerm` and `azapi` providers.

1. Copy `terraform/terraform.tfvars.example` to `terraform.tfvars` (or provide variables inline). Required variables mirror the Bicep parameters:
   ```hcl
   resource_group_name          = "<rg-name>"
   account_base_name            = "foundry"
   location                     = "eastus"
   project_display_name         = "Foundry Project"
   project_description          = "Sample AI Foundry project deployment."
   existing_vnet_resource_id    = "/subscriptions/<...>/virtualNetworks/<...>"
   new_pe_subnet_name           = "foundry-pe-subnet"
   new_pe_subnet_prefix         = "192.168.10.0/24"
   new_agent_subnet_name        = "foundry-agent-subnet"
   new_agent_subnet_prefix      = "192.168.11.0/24"
   existing_aoai_resource_id    = "/subscriptions/<...>/accounts/<...>"
   ```
2. Initialize and apply:
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```
3. Review the outputs for the account ID, name, endpoint, project name, and BYO connection resource ID.

## Resource & Permission Diagram

```mermaid
graph TD
    Deployer["Deployment Principal\n(Contributor on RG)"]
    ExistingAOAI["Existing Azure OpenAI Account\n(existingAoaiResource)"]

    subgraph ExistingVNet["Existing Virtual Network\n(existingVnet)"]
        NewSubnet["New Private Endpoint Subnet\n(privateEndpointSubnet)"]
        AgentSubnet["New Agent Subnet\n(agentSubnet)"]
    end

    subgraph RG["Resource Group"]
        DNSAIServices["Private DNS Zone\n(aiServicesPrivateDnsZone)"]
        DNSOpenAI["Private DNS Zone\n(openAiPrivateDnsZone)"]
        DNSCog["Private DNS Zone\n(cognitiveServicesPrivateDnsZone)"]
        PE["Private Endpoint\naiAccountPrivateEndpoint"]
        Account["AI Foundry Account\n(aiFoundry)"]
        Project["AI Foundry Project\n(project)"]
        Connection["BYO Azure OpenAI Connection\n(project::byoAoaiConnection)"]
        AccountHost["Account Capability Host\n(accountCapabilityHost)"]
        ProjectHost["Project Capability Host\n(projectCapabilityHost)"]
    end

    Deployer -->|"creates"| RG
    NewSubnet --> PE
    AgentSubnet -->|"network injection"| Account
    PE -->|"private link"| Account
    DNSAIServices -. "vNet link" .-> ExistingVNet
    DNSOpenAI -. "vNet link" .-> ExistingVNet
    DNSCog -. "vNet link" .-> ExistingVNet
    PE -->|"DNS zone group"| DNSAIServices
    PE -->|"DNS zone group"| DNSOpenAI
    PE -->|"DNS zone group"| DNSCog
    Account --> Project
    Project --> Connection
    Account --> AccountHost
    Project --> ProjectHost
    Connection -->|"AAD connection"| ExistingAOAI

    AccountMI["Account Managed Identity"] -->|"Cognitive Services OpenAI User"| ExistingAOAI
    ProjectMI["Project Managed Identity"] -->|"Cognitive Services OpenAI User (recommended)"| ExistingAOAI
```

## Outputs
The deployment emits the Foundry account ID, name, endpoint, project name, and the fully qualified resource ID of the project connection (`projectConnectionName`).

## Notes
- The template creates new subnets in your existing VNet for both private endpoints and agent workloads. Confirm you have permission to modify the virtual network and that required route/firewall rules exist.
- Private DNS zones are created in the deployment resource group and linked to your VNet. Skip linking if your environment already centralizes these zones.
- Access to the AI Foundry endpoint requires connectivity to the specified virtual network.
