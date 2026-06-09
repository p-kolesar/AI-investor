// =============================================================================
// AI-investor - core infrastructure (Python Function App on Flex Consumption)
// Deployed at resource-group scope. The resource group is created by the
// infra GitHub workflow before this template runs.
// =============================================================================

targetScope = 'resourceGroup'

@description('Base name used to derive all resource names (lowercase alphanumeric).')
param baseName string = 'aiinvestor'

@description('Short environment name, e.g. dev / prod.')
param environmentName string = 'dev'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Python version for the Function App runtime.')
param pythonVersion string = '3.13'

@description('Finnhub API key (passed from a GitHub secret).')
@secure()
param finnhubApiKey string

@description('Claude API key (passed from a GitHub secret).')
@secure()
param claudeApiKey string

// ---- Derived names ----------------------------------------------------------
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageAccountName = take(toLower('st${baseName}${environmentName}${uniqueSuffix}'), 24)
var functionAppName = 'func-${baseName}-${environmentName}-${uniqueSuffix}'
var hostingPlanName = 'plan-${baseName}-${environmentName}'
var appInsightsName = 'appi-${baseName}-${environmentName}'
var logAnalyticsName = 'log-${baseName}-${environmentName}'
var staticSiteProdName = 'stapp-${baseName}-${environmentName}-prod-${uniqueSuffix}'
var deploymentContainerName = 'deploymentpackage'
var dataContainerName = 'papertrading'
var deploymentStorageConnSettingName = 'DEPLOYMENT_STORAGE_CONNECTION_STRING'

// ---- Storage ----------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: {
    publicAccess: 'None'
  }
}

// Application data container (Parquet files: portfolio, trades, cache, …).
// Also created at runtime by the backend, but declared here so infra owns it.
resource dataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: dataContainerName
  properties: {
    publicAccess: 'None'
  }
}


var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'

// ---- Observability ----------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---- Flex Consumption hosting plan -----------------------------------------
resource hostingPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: hostingPlanName
  location: location
  kind: 'functionapp'
  sku: {
    tier: 'FlexConsumption'
    name: 'FC1'
  }
  properties: {
    reserved: true
  }
}

// ---- Function App (Flex Consumption, Python) -------------------------------
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: hostingPlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}${deploymentContainerName}'
          authentication: {
            type: 'StorageAccountConnectionString'
            storageAccountConnectionStringName: deploymentStorageConnSettingName
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 40
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: pythonVersion
      }
    }
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: deploymentStorageConnSettingName
          value: storageConnectionString
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'FINNHUB_API_KEY'
          value: finnhubApiKey
        }
        {
          name: 'CLAUDE_API_KEY'
          value: claudeApiKey
        }
      ]
      // The Static Web App calls this API cross-origin (build-time
      // VITE_API_BASE = https://<func-host>/api). Allow its generated hostname;
      // Bicep resolves the dependency so the SWA is created first.
      cors: {
        allowedOrigins: [
          'https://${staticSiteProd.properties.defaultHostname}'
        ]
      }
    }
  }
}

// ---- Static Web App (Free) --------------------------------------------------
// Public, no-auth SPA (prod) for the workshop. Deployed via the SWA GitHub
// Action with a deployment token (provider: None = no SWA-managed repo
// integration). Free tier keeps this within the demo's cost budget.
// NOTE: Static Web Apps are only offered in a subset of regions
// (e.g. westeurope, eastus2, westus2, centralus, eastasia).
// A second SWA for frontend-beta will be added alongside Phase 4.
resource staticSiteProd 'Microsoft.Web/staticSites@2024-04-01' = {
  name: staticSiteProdName
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    provider: 'None'
  }
}

// ---- Outputs ----------------------------------------------------------------
output functionAppName string = functionApp.name
output functionAppDefaultHostname string = functionApp.properties.defaultHostName
output storageAccountName string = storageAccount.name
output resourceGroupName string = resourceGroup().name
output staticWebAppProdName string = staticSiteProd.name
output staticWebAppProdHostname string = staticSiteProd.properties.defaultHostname
