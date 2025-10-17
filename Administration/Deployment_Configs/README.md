# Deployment Configurations

This directory contains reusable deployment scenarios for Azure AI Foundry and its related resources. Each scenario comes with both Bicep and Terraform implementations (unless noted otherwise) plus supporting documentation to help you configure the required parameters.

Use the summaries below to pick the template that best matches your environment, then drill into the linked folder for detailed instructions.

## Available Scenarios

- [**BYO_AOAI_wPrivate_Networking**](BYO_AOAI_wPrivate_Networking)
  - Provisions a new virtual network, dedicated subnets (private endpoint + agent), AI Foundry account, project, and a bring-your-own Azure OpenAI connection.
  - Ideal when you want a self-contained deployment that sets up networking from scratch.
- [**BYO_AOAI_wExisting_VNET_wNewSubnet**](BYO_AOAI_wExisting_VNET_wNewSubnet)
  - Reuses an existing virtual network, creates the necessary private endpoint and agent subnets, and deploys AI Foundry with a BYO Azure OpenAI connection.
  - Choose this when your network team owns the VNet but allows Terraform/Bicep to add new subnets.
- [**BYO_AOAI_wExisting_VNet**](BYO_AOAI_wExisting_VNet)
  - Targets fully pre-created networking: both the private endpoint subnet and the agent subnet already exist, and the templates wire AI Foundry into them alongside a BYO Azure OpenAI connection.
  - Best for environments with strict network-change controls where subnets are managed outside the deployment.
- [**Existing_AIFoundryProject_wConnections**](Existing_AIFoundryProject_wConnections)
  - Assumes an AI Foundry account already exists. Deploys new projects plus multiple connection types (Azure OpenAI, API endpoints, etc.) into that account.
  - Useful for layering additional integrations on top of an established Foundry environment.
- [**Existing_AIFoundryProject_wAOAIConnection**](Existing_AIFoundryProject_wAOAIConnection)
  - Similar to the previous scenario but focused on creating a single project that connects to an existing Azure OpenAI resource.
  - Good starting point when you only need a project + AOAI wiring without other connection types.

## How to Use These Templates

1. Pick the scenario that matches your deployment posture.
2. Read the scenario-specific README for prerequisites and variable descriptions.
3. Provide parameter values via `main.parameters.json` (Bicep) or `terraform.tfvars` (Terraform).
4. Run the provided deployment commands (`az deployment group create` or `terraform apply`).

All templates rely on the Azure AzAPI provider/resource type versions noted in their manifests. Review the scenario documentation for any additional role assignments, feature flags, or cleanup guidance.

## Step-by-Step Provisioning Process

1. Create the project-dependent resources required for the standard setup:
   - Create new (or supply the resource ID of an existing) Cosmos DB resource.
   - Create new (or supply the resource ID of an existing) Azure Storage resource.
   - Create new (or supply the resource ID of an existing) Azure AI Search resource.
   - Create a new Key Vault resource.
   - *Optional:* Create a new Application Insights resource.
   - *Optional:* Provide the resource ID of an existing AI Foundry resource if you do not want to create a new one later.
2. Create the Azure AI Foundry resource (`Microsoft.CognitiveServices/accounts` with `kind = AIServices`).
3. Establish account-level connections:
   - Create the account connection to the Application Insights resource.
   - Deploy `gpt-4o` or another agent-compatible model into the account.
4. Create the project (`Microsoft.CognitiveServices/accounts/projects`).
5. Configure project connections:
   - If provided, add the project connection to the existing AI Foundry resource.
   - Create project connections to the Azure Storage account, Azure AI Search account, and Cosmos DB account.
6. Assign the project-managed identity (including the system-managed identity) the following roles:
   - Cosmos DB Operator at the account scope for the Cosmos DB resource.
   - Storage Account Contributor at the account scope for the Storage Account resource.
7. Set capability hosts:
   - Configure the account capability host with an empty `properties` block.
   - Configure the project capability host with references to the Cosmos DB, Azure Storage, and Azure AI Search connections.
8. Grant the project-managed identity (system- and user-assigned) the required resource-level roles:
   - **Azure AI Search** (before or after capability host creation): assign `Search Index Data Contributor` and `Search Service Contributor`.
   - **Azure Blob Storage container** `\<workspaceId\>-azureml-blobstore`: assign `Storage Blob Data Contributor`.
   - **Azure Blob Storage container** `\<workspaceId\>-agents-blobstore`: assign `Storage Blob Data Owner`.
   - **Cosmos DB for NoSQL container** `\<${projectWorkspaceId}>-thread-message-store`: assign `Cosmos DB Built-in Data Contributor`.
   - **Cosmos DB for NoSQL container** `\<${projectWorkspaceId}>-agent-entity-store`: assign `Cosmos DB Built-in Data Contributor`.
9. After all resources are provisioned, grant every developer who needs to create or edit agents in the project the `Azure AI User` role at the project scope.

## End-to-End Architecture (Mermaid Overview)

```mermaid
graph TD
    subgraph Subscription
        RG[Resource Group]
    end

    subgraph Networking
        VNet[Virtual Network]
        PeSubnet[Private Endpoint Subnet]
        AgentSubnet[Agent Subnet]
        PrivateEndpoint[Private Endpoint]
    end

    subgraph DataAndMonitoring
        Cosmos[Cosmos DB]
        Storage[Azure Storage]
        Search[Azure AI Search]
        KeyVault[Key Vault]
        AppInsights[Application Insights]
    end

    subgraph Foundry
        Account[AI Foundry Account]
        Model[GPT-4o / Agent Model Deployment]
        AccountConnections[Account Connections]
        Project[AI Foundry Project]
        ProjectConnections[Project Connections]
        AccountCapHost[Account Capability Host]
        ProjectCapHost[Project Capability Host]
    end

    subgraph Identity
        ProjectMI[Project Managed Identity (SMI/UMI)]
        Developers[Developers]
    end

    RG --> VNet
    VNet --> PeSubnet
    VNet --> AgentSubnet
    PeSubnet --> PrivateEndpoint
    PrivateEndpoint --> Account

    Account --> Model
    Account --> AccountConnections
    AccountConnections --> AppInsights

    Project --> ProjectConnections
    ProjectConnections --> Storage
    ProjectConnections --> Search
    ProjectConnections --> Cosmos

    ProjectConnections --> Account
    KeyVault --> Account
    Account --> AccountCapHost
    Project --> ProjectCapHost
    ProjectCapHost --> Storage
    ProjectCapHost --> Search
    ProjectCapHost --> Cosmos

    ProjectMI --> Storage
    ProjectMI --> Search
    ProjectMI --> Cosmos

    Developers -->|Azure AI User Role| Project
```
