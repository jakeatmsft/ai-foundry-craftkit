# Azure AI Foundry Account Only (Bicep)

This Bicep template provisions an Azure AI Foundry account (`Microsoft.CognitiveServices/accounts` with `kind = AIServices`) and, by default, a single `gpt-5-mini` model deployment inside that account. It does not create projects, connections, private endpoints, virtual networks, or any supporting data services.

## What gets deployed
- Azure AI Foundry account with SKU `S0`.
- System-assigned managed identity on the account.
- Default `gpt-5-mini` model deployment using version `2025-08-07`, `GlobalStandard` SKU, and capacity `10`.
- Optional account settings for public network access, local auth, future project management, and whether the model deployment should be skipped.

## Common inputs
- `accountBaseName`: Base string for the account name. The template appends a 4-character suffix for uniqueness.
- `location`: Azure region for the account.
- `publicNetworkAccess`: Defaults to `Enabled`. Set to `Disabled` only if you plan to add private connectivity separately.
- `disableLocalAuth`: Optional hardening flag for disabling API-key style auth.
- `allowProjectManagement`: Keeps the account ready for later project creation without creating a project now.
- `customSubDomainName`: Optional override for the account subdomain. Leave blank to reuse the generated account name.
- `deployModel`: Defaults to `true`. Set to `false` if you want the original account-only behavior.
- `modelDeploymentName`, `modelVersion`, `modelSkuName`, `modelCapacity`: Control the default `gpt-5-mini` deployment created in the account.

## Deploy
1. Create or select the resource group that will host the AI Foundry account.
2. Update `main.parameters.json` with your environment-specific values.
3. Deploy the template:
   ```bash
   az deployment group create \
     --resource-group <resource-group-name> \
     --template-file main.bicep \
     --parameters @main.parameters.json
   ```

## Outputs
- `accountId` - Resource ID of the AI Foundry account.
- `accountNameOut` - Name of the AI Foundry account.
- `accountEndpoint` - Endpoint URI for the account.
- `managedIdentityPrincipalId` - Principal ID of the system-assigned managed identity.
- `modelDeploymentId` - Resource ID of the `gpt-5-mini` deployment when `deployModel` is `true`.
- `modelDeploymentNameOut` - Deployment name when `deployModel` is `true`.
