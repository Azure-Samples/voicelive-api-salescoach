targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string = 'swedencentral'

@description('Id of the user or app to assign application roles')
param principalId string = ''

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

module main 'main-resources.bicep' = {
  name: 'main-resources'
  scope: rg
  params: {
    environmentName: environmentName
    principalId: principalId
  }
}

output AZURE_CONTAINER_APP_ENVIRONMENT_NAME string = main.outputs.AZURE_CONTAINER_APP_ENVIRONMENT_NAME
output AZURE_CONTAINER_APP_NAME string = main.outputs.AZURE_CONTAINER_APP_NAME
output SERVICE_VOICELAB_SALES_TRAINING_URI string = main.outputs.SERVICE_VOICELAB_SALES_TRAINING_URI
output PROJECT_ENDPOINT string = main.outputs.PROJECT_ENDPOINT
output AZURE_OPENAI_ENDPOINT string = main.outputs.AZURE_OPENAI_ENDPOINT
output AZURE_SPEECH_REGION string = main.outputs.AZURE_SPEECH_REGION
output AI_FOUNDRY_RESOURCE_NAME string = main.outputs.AI_FOUNDRY_RESOURCE_NAME
