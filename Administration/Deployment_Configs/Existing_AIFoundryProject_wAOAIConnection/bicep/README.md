# Existing AI Foundry Project With Azure OpenAI Connection (Bicep)

This Bicep template provisions a new Azure AI Foundry project inside an existing account, establishes a bring-your-own (BYO) Azure OpenAI connection, and configures a project-level capability host for Agents workloads.

## What gets deployed
- AI Foundry project (`Microsoft.CognitiveServices/accounts/projects`) with a system-assigned managed identity.
- Single project connection (`connections@2025-06-01`) pointing at an existing Azure OpenAI resource.
- Project capability host (`capabilityHosts@2025-04-01-preview`) associated with the Azure OpenAI connection name.

## Required inputs
- `existingAiFoundryAccountResourceId`: Resource ID of the AI Foundry account that will host the project.
- `azureOpenAiResourceId`: Resource ID of the Azure OpenAI account to connect.

Optional parameters allow overriding the project name, display metadata, and capability host name.

## Deploy
1. Create or select a resource group that contains the existing AI Foundry account.
2. Update `main.parameters.json` with your environment-specific values.
3. Deploy the template:
   ```bash
   az deployment group create \
     --resource-group <resource-group-containing-foundry> \
     --template-file main.bicep \
     --parameters @main.parameters.json
   ```

The deploying principal must have permissions to read the existing AI Foundry and Azure OpenAI resources and to create child resources (project, connection, capability host).

## Outputs
- `projectId` – Resource ID of the AI Foundry project.
- `projectNameOut` – Name of the project resource.
- `capabilityHostId` – Resource ID of the capability host.
- `projectConnectionId` – Resource ID of the Azure OpenAI connection created inside the project.
