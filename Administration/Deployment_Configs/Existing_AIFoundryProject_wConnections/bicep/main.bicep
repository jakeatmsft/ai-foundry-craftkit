/*
  Deploys a project against an existing AI Foundry account, establishes BYO connections
  for Azure OpenAI, Azure AI Search, Azure Cosmos DB, and Azure Storage, and provisions
  an Agents capability host bound to those connections.
*/

@description('Resource ID of the existing AI Foundry account that will host the project.')
param existingAiFoundryAccountResourceId string

@description('Optional project resource name. Leave blank to default to <account-name>-proj.')
param projectName string = ''

@description('Display name applied to the AI Foundry project.')
param projectDisplayName string = 'Project Display Name'

@description('Description stored on the AI Foundry project.')
param projectDescription string = 'Sample project provisioned by Bicep.'

@description('Resource ID of the existing Azure OpenAI account that the project will connect to.')
param azureOpenAiResourceId string

@description('Name assigned to the Azure OpenAI project connection.')
param azureOpenAiConnectionName string = 'aoaiConnection'

@description('Optional key/value pairs appended to the Azure OpenAI connection metadata payload.')
param azureOpenAiAdditionalMetadata object = {}

@description('Resource ID of the existing Azure AI Search service that the project will connect to.')
param azureAiSearchResourceId string

@description('Name of the Azure AI Search index exposed to the project connection.')
param azureAiSearchIndexName string

@description('Optional semantic configuration name to associate with the Azure AI Search connection.')
param azureAiSearchSemanticConfigurationName string = ''

@description('Name assigned to the Azure AI Search project connection.')
param azureAiSearchConnectionName string = 'aiSearchConnection'

@description('Optional key/value pairs appended to the Azure AI Search connection metadata payload.')
param azureAiSearchAdditionalMetadata object = {}

@description('Resource ID of the existing Azure Cosmos DB account that the project will connect to.')
param cosmosAccountResourceId string

@description('Name of the Cosmos DB database exposed to the project connection.')
param cosmosDatabaseName string

@description('Name of the Cosmos DB container exposed to the project connection.')
param cosmosContainerName string

@description('Name assigned to the Cosmos DB project connection.')
param cosmosConnectionName string = 'cosmosConnection'

@description('Optional key/value pairs appended to the Cosmos DB connection metadata payload.')
param cosmosAdditionalMetadata object = {}

@description('Resource ID of the existing Azure Storage account that the project will connect to.')
param storageAccountResourceId string

@description('Name of the Azure Storage container/queue/table/share exposed to the project connection.')
param storageContainerName string

@allowed([
  'Blob'
  'Queue'
  'Table'
  'File'
])
@description('Storage service surface to expose through the connection (Blob, Queue, Table, or File).')
param storageService string = 'Blob'

@description('Name assigned to the Azure Storage project connection.')
param storageConnectionName string = 'storageConnection'

@description('Optional key/value pairs appended to the Azure Storage connection metadata payload.')
param storageAdditionalMetadata object = {}

@description('Optional name for the project capability host. Leave blank to default to <project-name>-capHost.')
param projectCapabilityHostName string = ''

// Helpers to derive names and scopes from the supplied resource IDs.
var accountResourceIdParts = split(existingAiFoundryAccountResourceId, '/')
var accountSubscriptionId = accountResourceIdParts[2]
var accountResourceGroupName = accountResourceIdParts[4]
var accountName = accountResourceIdParts[8]

var azureOpenAiIdParts = split(azureOpenAiResourceId, '/')
var azureOpenAiSubscriptionId = azureOpenAiIdParts[2]
var azureOpenAiResourceGroupName = azureOpenAiIdParts[4]
var azureOpenAiAccountName = azureOpenAiIdParts[8]

var azureAiSearchIdParts = split(azureAiSearchResourceId, '/')
var azureAiSearchSubscriptionId = azureAiSearchIdParts[2]
var azureAiSearchResourceGroupName = azureAiSearchIdParts[4]
var azureAiSearchServiceName = azureAiSearchIdParts[8]

var cosmosAccountIdParts = split(cosmosAccountResourceId, '/')
var cosmosSubscriptionId = cosmosAccountIdParts[2]
var cosmosResourceGroupName = cosmosAccountIdParts[4]
var cosmosAccountName = cosmosAccountIdParts[8]

var storageAccountIdParts = split(storageAccountResourceId, '/')
var storageSubscriptionId = storageAccountIdParts[2]
var storageResourceGroupName = storageAccountIdParts[4]
var storageAccountName = storageAccountIdParts[8]

var effectiveProjectName = empty(projectName) ? '${accountName}-proj' : projectName
var effectiveCapabilityHostName = empty(projectCapabilityHostName) ? '${effectiveProjectName}-capHost' : projectCapabilityHostName

var storageServiceKey = toLower(storageService)
var azureOpenAiTarget = existingAzureOpenAi.properties.endpoint
var azureAiSearchTarget = empty(existingAzureAiSearch.properties.hostName) ? existingAzureAiSearch.properties.endpoint : 'https://${existingAzureAiSearch.properties.hostName}'
var cosmosTarget = existingCosmosAccount.properties.documentEndpoint

resource existingAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  scope: resourceGroup(accountSubscriptionId, accountResourceGroupName)
  name: accountName
}

resource existingAzureOpenAi 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  scope: resourceGroup(azureOpenAiSubscriptionId, azureOpenAiResourceGroupName)
  name: azureOpenAiAccountName
}

resource existingAzureAiSearch 'Microsoft.Search/searchServices@2023-11-01' existing = {
  scope: resourceGroup(azureAiSearchSubscriptionId, azureAiSearchResourceGroupName)
  name: azureAiSearchServiceName
}

resource existingCosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  scope: resourceGroup(cosmosSubscriptionId, cosmosResourceGroupName)
  name: cosmosAccountName
}

resource existingStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  scope: resourceGroup(storageSubscriptionId, storageResourceGroupName)
  name: storageAccountName
}

var azureOpenAiMetadata = union({
    ApiType: 'Azure'
    ResourceId: azureOpenAiResourceId
    location: existingAzureOpenAi.location
  }, azureOpenAiAdditionalMetadata)

var azureAiSearchMetadata = union({
    ResourceId: azureAiSearchResourceId
    IndexName: azureAiSearchIndexName
  }, empty(azureAiSearchSemanticConfigurationName) ? {} : {
    SemanticConfiguration: azureAiSearchSemanticConfigurationName
  }, azureAiSearchAdditionalMetadata)

var cosmosMetadata = union({
    ResourceId: cosmosAccountResourceId
    AccountName: cosmosAccountName
    DatabaseName: cosmosDatabaseName
    ContainerName: cosmosContainerName
    AccountEndpoint: existingCosmosAccount.properties.documentEndpoint
  }, cosmosAdditionalMetadata)

var storageMetadata = union({
    ResourceId: storageAccountResourceId
    StorageAccountName: storageAccountName
    ContainerName: storageContainerName
    StorageService: storageService
  }, storageAdditionalMetadata)

var storagePrimaryEndpoints = existingStorageAccount.properties.primaryEndpoints
var storageTarget = contains(storagePrimaryEndpoints, storageServiceKey) ? storagePrimaryEndpoints[storageServiceKey] : ''

assert(!empty(azureOpenAiTarget), 'Resolved Azure OpenAI endpoint is empty; verify azureOpenAiResourceId.')
assert(!empty(azureAiSearchTarget), 'Resolved Azure AI Search endpoint is empty; verify azureAiSearchResourceId.')
assert(!empty(cosmosTarget), 'Resolved Cosmos DB endpoint is empty; verify cosmosAccountResourceId.')
assert(!empty(storageTarget), 'Resolved Storage endpoint is empty; verify storageAccountResourceId and storageService.')

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

resource azureOpenAiConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: azureOpenAiConnectionName
  properties: {
    category: 'AzureOpenAI'
    target: azureOpenAiTarget
    authType: 'AAD'
    metadata: azureOpenAiMetadata
  }
  dependsOn: [
    project
  ]
}

resource azureAiSearchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: azureAiSearchConnectionName
  properties: {
    category: 'AzureAISearch'
    target: azureAiSearchTarget
    authType: 'AAD'
    metadata: azureAiSearchMetadata
  }
  dependsOn: [
    project
  ]
}

resource cosmosConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: cosmosConnectionName
  properties: {
    category: 'AzureCosmosDB'
    target: cosmosTarget
    authType: 'AAD'
    metadata: cosmosMetadata
  }
  dependsOn: [
    project
  ]
}

resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: storageConnectionName
  properties: {
    category: 'AzureStorage'
    target: storageTarget
    authType: 'AAD'
    metadata: storageMetadata
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
      azureOpenAiConnectionName
      azureAiSearchConnectionName
      cosmosConnectionName
      storageConnectionName
    ]
  }
  dependsOn: [
    azureOpenAiConnection
    azureAiSearchConnection
    cosmosConnection
    storageConnection
  ]
}

output projectId string = project.id
output projectNameOut string = project.name
output capabilityHostId string = capabilityHost.id
output projectConnections array = [
  {
    name: azureOpenAiConnectionName
    resourceId: azureOpenAiConnection.id
  }
  {
    name: azureAiSearchConnectionName
    resourceId: azureAiSearchConnection.id
  }
  {
    name: cosmosConnectionName
    resourceId: cosmosConnection.id
  }
  {
    name: storageConnectionName
    resourceId: storageConnection.id
  }
]
