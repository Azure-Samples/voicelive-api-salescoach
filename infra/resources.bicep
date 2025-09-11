@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}

param voicelabExists bool

param useFoundryAgents bool

@description('Id of the user or app to assign application roles')
param principalId string

@description('Principal type of user or app')
param principalType string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

var projectName = 'voicelab-project-${resourceToken}'

param gptModelName string = 'gpt-4o'
param gptModelVersion string = '2024-08-06'
param gptDeploymentName string = 'gpt-4o'

param openAiModelDeployments array = [
  {
    name: gptDeploymentName
    model: gptModelName
    version: gptModelVersion
    sku: {
      name: 'Standard'
      capacity: 10
    }
  }
  {
    name: 'text-embedding-ada-002'
    model: 'text-embedding-ada-002'
    sku: {
      name: 'Standard'
      capacity: 10
    }
  }
]

resource aiFoundryResource 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'aifoundry-voicelab-${resourceToken}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: 'aifoundry-voicelab-${resourceToken}'
    publicNetworkAccess: 'Enabled'
  }

  @batchSize(1)
  resource deployment 'deployments' = [
    for deployment in openAiModelDeployments: {
      name: deployment.name
      sku: deployment.?sku ?? {
        name: 'Standard'
        capacity: 20
      }
      properties: {
        model: {
          format: 'OpenAI'
          name: deployment.model
          version: deployment.?version ?? null
        }
        raiPolicyName: deployment.?raiPolicyName ?? null
        versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
      }
    }
  ]

  resource project 'projects@2025-06-01' = {
    name: projectName
    location: location
    identity: {
      type: 'SystemAssigned'
    }
    properties: {
      description: 'Default project'
      displayName: 'Default Project'
    }
  }
}

resource speechService 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'speech-voicelab-${resourceToken}'
  location: location
  tags: tags
  kind: 'SpeechServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'speech-voicelab-${resourceToken}'
    publicNetworkAccess: 'Enabled'
  }
}

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}
// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    publicNetworkAccess: 'Enabled'
    roleAssignments: [
      {
        principalId: voicelabIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId(
          'Microsoft.Authorization/roleDefinitions',
          '7f951dda-4ed3-4680-a7ca-43fe172d538d'
        )
      }
    ]
  }
}

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

module voicelabIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'voicelabidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}voicelab-${resourceToken}'
    location: location
  }
}
module voicelabFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'voicelab-fetch-image'
  params: {
    exists: voicelabExists
    name: 'voicelab'
  }
}

module voicelab 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'voicelab'
  params: {
    name: 'voicelab'
    ingressTargetPort: 8000
    ingressExternal: true
    ingressTransport: 'http'
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList: [
         {
          name: 'ai-foundry-api-key'
          value: aiFoundryResource.listKeys().key1
        }
        {
          name: 'speech-api-key'
          value: speechService.listKeys().key1
        }
      ]
    }
    containers: [
      {
        image: voicelabFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('1.0')
          memory: '2.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: voicelabIdentity.outputs.clientId
          }
          {
            name: 'AZURE_OPENAI_ENDPOINT'
            value: aiFoundryResource.properties.endpoint
          }
          {
            name: 'AZURE_OPENAI_API_KEY'
            secretRef: 'ai-foundry-api-key'
          }
          {
            name: 'PROJECT_ENDPOINT'
            value: '${aiFoundryResource.properties.endpoint}api/projects/${projectName}'
          }
          {
            name: 'MODEL_DEPLOYMENT_NAME'
            value: gptDeploymentName
          }
          {
            name: 'AZURE_SPEECH_KEY'
            secretRef: 'speech-api-key'
          }
          {
            name: 'AZURE_SPEECH_REGION'
            value: 'swedencentral'
          }
          {
            name: 'AZURE_AI_RESOURCE_NAME'
            value: aiFoundryResource.name
          }
          {
            name: 'AZURE_AI_REGION'
            value: 'swedencentral'
          }
          {
            name: 'SUBSCRIPTION_ID'
            value: subscription().subscriptionId
          }
          {
            name: 'RESOURCE_GROUP_NAME'
            value: resourceGroup().name
          }
          {
            name: 'USE_AZURE_AI_AGENTS'
            value: useFoundryAgents ? 'true' : 'false'
          }
          {
            name: 'PORT'
            value: '8000'
          }
          {
            name: 'HOST'
            value: '0.0.0.0'
          }
        ]
      }
    ]
    managedIdentities: {
      systemAssigned: false
      userAssignedResourceIds: [voicelabIdentity.outputs.resourceId]
    }
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: voicelabIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'voicelab' })
  }
}

resource containerAppAzureAIDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, voicelab.name, '64702f94-c441-49e6-a78b-ef80e0188fee')
  properties: {
    principalId: voicelabIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

resource containerAppCognitiveServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, voicelab.name, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    principalId: voicelabIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

resource containerAppCognitiveServicesOpenAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, voicelab.name, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  properties: {
    principalId: voicelabIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

resource userAzureAIDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '64702f94-c441-49e6-a78b-ef80e0188fee')
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

resource userCognitiveServicesOpenAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(resourceGroup().id, principalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_VOICELAB_ID string = voicelab.outputs.resourceId
output AZURE_CONTAINER_APP_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output AZURE_CONTAINER_APP_NAME string = voicelab.name
output SERVICE_VOICELAB_URI string = 'https://${voicelab.outputs.fqdn}'
output AZURE_TENANT_ID string = subscription().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output VOICELAB_IDENTITY_PRINCIPAL_ID string = voicelabIdentity.outputs.principalId
output PROJECT_ENDPOINT string = '${aiFoundryResource.properties.endpoint}api/projects/default-project'
output AZURE_OPENAI_ENDPOINT string = aiFoundryResource.properties.endpoint
output AZURE_SPEECH_REGION string =  location
output AI_FOUNDRY_RESOURCE_NAME string = aiFoundryResource.name
