/*
  Deploys an Azure AI Foundry account and an optional default model deployment.

  Description:
  - Creates a Microsoft.CognitiveServices/accounts resource with kind = AIServices.
  - Optionally creates an account-level gpt-5-mini deployment.
  - Does not create projects, connections, networking, or supporting services.
*/

@maxLength(9)
@description('Base name for the AI Foundry account. A random suffix is appended to ensure uniqueness.')
param accountBaseName string = 'foundry'

@description('Optional explicit AI Foundry account name. Leave blank to use the generated name based on accountBaseName.')
param accountName string = ''

@allowed([
  'australiaeast'
  'canadaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'koreacentral'
  'norwayeast'
  'polandcentral'
  'southindia'
  'swedencentral'
  'switzerlandnorth'
  'uaenorth'
  'uksouth'
  'westus'
  'westus3'
  'westeurope'
  'southeastasia'
])
@description('The Azure region where the AI Foundry account will be created.')
param location string = 'eastus'

@allowed([
  'Enabled'
  'Disabled'
])
@description('Controls whether the AI Foundry account is reachable over the public internet. If set to Disabled, provide private connectivity separately.')
param publicNetworkAccess string = 'Enabled'

@description('Controls whether API keys and other local auth methods are disabled on the AI Foundry account.')
param disableLocalAuth bool = false

@description('Controls whether projects can be created under this AI Foundry account later.')
param allowProjectManagement bool = true

@description('Optional custom subdomain name. Leave blank to reuse the generated account name.')
param customSubDomainName string = ''

@description('Controls whether a default gpt-5-mini deployment is created in the AI Foundry account.')
param deployModel bool = true

@description('Name of the AI Foundry model deployment resource.')
param modelDeploymentName string = 'gpt-5-mini'

@description('Version of the gpt-5-mini model to deploy.')
param modelVersion string = '2025-08-07'

@description('SKU name for the model deployment (for example, GlobalStandard or Standard).')
param modelSkuName string = 'GlobalStandard'

@minValue(1)
@description('Capacity assigned to the model deployment.')
param modelCapacity int = 10

var generatedAiFoundryName string = '${accountBaseName}${substring(uniqueString(resourceGroup().id, accountBaseName), 0, 4)}'
var aiFoundryName string = empty(accountName) ? generatedAiFoundryName : toLower(accountName)
var effectiveCustomSubDomainName string = empty(customSubDomainName) ? aiFoundryName : customSubDomainName

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiFoundryName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: allowProjectManagement
    customSubDomainName: effectiveCustomSubDomainName
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: publicNetworkAccess
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployModel) {
  parent: aiFoundry
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: modelVersion
    }
  }
}

output accountId string = aiFoundry.id
output accountNameOut string = aiFoundry.name
output accountEndpoint string = aiFoundry.properties.endpoint
output managedIdentityPrincipalId string = aiFoundry.identity.principalId
output modelDeploymentId string = deployModel ? modelDeployment.id : ''
output modelDeploymentNameOut string = deployModel ? modelDeployment.name : ''
