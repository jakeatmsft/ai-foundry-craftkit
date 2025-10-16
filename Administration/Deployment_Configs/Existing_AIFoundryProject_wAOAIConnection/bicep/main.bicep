/*
  Deploys a project against an existing AI Foundry account, establishes a BYO Azure OpenAI
  connection, and provisions an Agents capability host bound to that connection.
*/

@description('Resource ID of the existing AI Foundry account that will host the project.')
param existingAiFoundryAccountResourceId string

@description('Resource ID of the existing Azure OpenAI account that the project will connect to.')
param azureOpenAiResourceId string

@description('Optional project resource name. Leave blank to default to <account-name>-proj.')
param projectName string = ''

@description('Display name applied to the AI Foundry project.')
param projectDisplayName string = 'Project Display Name'

@description('Description stored on the AI Foundry project.')
param projectDescription string = 'Sample project provisioned by Bicep.'

@description('Optional name for the project capability host. Leave blank to default to <project-name>-capHost.')
param projectCapabilityHostName string = ''

var accountParts = split(existingAiFoundryAccountResourceId, '/')
var accountSubscriptionId = accountParts[2]
var accountResourceGroupName = accountParts[4]
var accountName = accountParts[8]

var azureOpenAiParts = split(azureOpenAiResourceId, '/')
var azureOpenAiSubscriptionId = azureOpenAiParts[2]
var azureOpenAiResourceGroupName = azureOpenAiParts[4]
var azureOpenAiAccountName = azureOpenAiParts[8]

var effectiveProjectName = empty(projectName) ? '${accountName}-proj' : projectName
var effectiveCapabilityHostName = empty(projectCapabilityHostName) ? '${effectiveProjectName}-capHost' : projectCapabilityHostName

resource existingAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  scope: resourceGroup(accountSubscriptionId, accountResourceGroupName)
  name: accountName
}

resource existingAzureOpenAi 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  scope: resourceGroup(azureOpenAiSubscriptionId, azureOpenAiResourceGroupName)
  name: azureOpenAiAccountName
}

var azureOpenAiMetadata = {
  ApiType: 'Azure'
  ResourceId: azureOpenAiResourceId
  location: existingAzureOpenAi.location
}

var azureOpenAiTarget = existingAzureOpenAi.properties.endpoint

assert(!empty(azureOpenAiTarget), 'Resolved Azure OpenAI endpoint is empty; verify azureOpenAiResourceId.')

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: existingAccount
  name: effectiveProjectName
  location: existingAccount.location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDescription
    displayName: projectDisplayName
  }
}

resource azureOpenAiConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: azureOpenAiAccountName
  properties: {
    name: azureOpenAiAccountName
    category: 'AzureOpenAI'
    target: azureOpenAiTarget
    authType: 'AAD'
    metadata: azureOpenAiMetadata
  }
  dependsOn: [
    project
  ]
}

resource capabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  parent: project
  name: effectiveCapabilityHostName
  properties: {
    capabilityHostKind: 'Agents'
    aiServicesConnections: [
      azureOpenAiAccountName
    ]
  }
  dependsOn: [
    azureOpenAiConnection
  ]
}

output projectId string = project.id
output projectNameOut string = project.name
output capabilityHostId string = capabilityHost.id
output projectConnectionId string = azureOpenAiConnection.id
