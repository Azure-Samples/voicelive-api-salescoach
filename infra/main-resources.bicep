@description('Name of the environment')
param environmentName string

@description('Principal ID for role assignments')
param principalId string = ''

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

var resourceToken = toLower(uniqueString(subscription().id, environmentName, 'swedencentral'))
var tags = { 'azd-env-name': environmentName }
var containerAppName = 'vst-${resourceToken}'

resource aiFoundryResource 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'aifoundry-voicelab-${resourceToken}'
  location: 'swedencentral'
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
}

resource speechService 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'speech-voicelab-${resourceToken}'
  location: 'swedencentral'
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

// Container Apps Environment
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-voicelab-${resourceToken}'
  location: 'swedencentral'
  tags: tags
  properties: {}
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: 'swedencentral'
  tags: union(tags, { 'azd-service-name': 'voicelab-sales-training' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      secrets: [
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
    template: {
      containers: [
        {
          image: 'ghcr.io/azure-samples/voicelive-api-salescoach:main'
          name: 'voicelab-sales-training'
          resources: {
            cpu: json('1.0')
            memory: '2.0Gi'
          }
          env: [
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
              value: '${aiFoundryResource.properties.endpoint}api/projects/default-project'
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
              value: 'false'
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
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

resource containerAppAzureAIDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, containerApp.name, '64702f94-c441-49e6-a78b-ef80e0188fee')
  properties: {
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

resource containerAppCognitiveServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, containerApp.name, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

resource containerAppCognitiveServicesOpenAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, containerApp.name, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  properties: {
    principalId: containerApp.identity.principalId
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

output AZURE_CONTAINER_APP_ENVIRONMENT_NAME string = containerAppsEnvironment.name
output AZURE_CONTAINER_APP_NAME string = containerApp.name
output SERVICE_VOICELAB_SALES_TRAINING_URI string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output AZURE_TENANT_ID string = subscription().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output CONTAINER_APP_IDENTITY_PRINCIPAL_ID string = containerApp.identity.principalId
output PROJECT_ENDPOINT string = '${aiFoundryResource.properties.endpoint}api/projects/default-project'
output AZURE_OPENAI_ENDPOINT string = aiFoundryResource.properties.endpoint
output AZURE_SPEECH_REGION string = 'swedencentral'
output AI_FOUNDRY_RESOURCE_NAME string = aiFoundryResource.name
