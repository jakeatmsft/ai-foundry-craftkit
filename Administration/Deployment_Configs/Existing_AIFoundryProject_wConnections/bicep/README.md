# Existing AI Foundry Project With Connections (Bicep)

This Bicep template provisions a new Azure AI Foundry project inside an **existing** AI Foundry account, creates bring-your-own (BYO) connections to existing Azure OpenAI, Azure AI Search, Azure Cosmos DB, and Azure Storage resources, and then configures an Agents capability host that binds to those connections.

## What gets deployed
- **AI Foundry project** (`Microsoft.CognitiveServices/accounts/projects`) with a system-assigned managed identity.
- **Project connections** for Azure OpenAI, Azure AI Search, Azure Cosmos DB, and Azure Storage that reference existing resources in your subscription(s).
- **Project-level capability host** (`capabilityHosts@2025-04-01-preview`) configured for the Agents capability and associated with every connection name.

## Required inputs
Collect the following values before deploying:
- Existing AI Foundry account resource ID, e.g. `/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>`
- Existing Azure OpenAI account resource ID.
- Existing Azure AI Search service resource ID and the index name you wish to expose.
- Existing Azure Cosmos DB account resource ID plus the target database and container names (SQL API expected).
- Existing Azure Storage account resource ID and the container/queue/table/share name to expose, along with the storage service type (`Blob`, `Queue`, `Table`, or `File`).

Optional parameters let you override connection names, provide semantic configuration names for Azure AI Search, and append additional metadata key/value pairs that your environment requires.

## Deploy
1. Create or select a resource group in a supported AI Foundry region (the template targets the resource group that contains the existing AI Foundry account).
2. Update `main.parameters.json` with your environment-specific values.
3. Run the deployment from any location that has access to the existing resources:
   ```bash
   az deployment group create \
     --resource-group <resource-group-containing-foundry> \
     --template-file main.bicep \
     --parameters @main.parameters.json
   ```

> **Note:** The account, Azure OpenAI, Azure AI Search, Cosmos DB, and Storage resources may reside in different subscriptions/resource groups; the template references them using cross-subscription `existing` declarations, so the deploying principal must have `Microsoft.CognitiveServices/*`, `Microsoft.Search/*`, `Microsoft.DocumentDB/*`, and `Microsoft.Storage/*` read permissions across those scopes.

## Outputs
- `projectId` – Resource ID of the AI Foundry project.
- `projectNameOut` – Name of the project resource.
- `capabilityHostId` – Resource ID of the capability host bound to the project.
- `projectConnections` – Array of objects listing the connection names and their corresponding resource IDs.

## Terraform equivalent
A Terraform configuration with equivalent behavior is available under `../terraform/`. Refer to its `README.md` for variable descriptions and usage.
