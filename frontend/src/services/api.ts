/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See LICENSE in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import {
  Assessment,
  AVATAR_OPTIONS,
  CustomScenarioData,
  Scenario,
} from '../types'

export interface AvatarConfig {
  character: string
  style: string
  is_photo_avatar: boolean
}

export function parseAvatarValue(value: string): AvatarConfig {
  const avatarOption = AVATAR_OPTIONS.find(opt => opt.value === value)
  const isPhotoAvatar = avatarOption?.isPhotoAvatar ?? false

  if (isPhotoAvatar) {
    return { character: value.toLowerCase(), style: '', is_photo_avatar: true }
  }

  const parts = value.split('-')
  const character = parts[0].toLowerCase()
  const style = parts.length >= 2 ? parts.slice(1).join('-') : 'casual-sitting'

  return { character, style, is_photo_avatar: false }
}

function extractUserText(conversationMessages: any[]): string {
  return conversationMessages
    .filter(msg => msg.role === 'user')
    .map(msg => msg.content)
    .join(' ')
    .trim()
}

export const api = {
  async getConfig() {
    const res = await fetch('/api/config')
    return res.json()
  },

  async getScenarios(): Promise<Scenario[]> {
    const res = await fetch('/api/scenarios')
    return res.json()
  },

  async createAgent(scenarioId: string, avatarConfig?: AvatarConfig) {
    const res = await fetch('/api/agents/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: scenarioId,
        avatar: avatarConfig,
      }),
    })
    if (!res.ok) throw new Error('Failed to create agent')
    return res.json()
  },

  /**
   * Create an agent with a custom scenario (not stored on server)
   * The scenario data is passed directly to the backend
   */
  async createAgentWithCustomScenario(
    scenarioId: string,
    scenarioData: CustomScenarioData,
    avatarConfig?: AvatarConfig
  ) {
    const res = await fetch('/api/agents/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        custom_scenario: {
          id: scenarioId,
          ...scenarioData,
        },
        avatar: avatarConfig,
      }),
    })
    if (!res.ok) throw new Error('Failed to create agent with custom scenario')
    return res.json()
  },

  async analyzeConversation(
    scenarioId: string,
    transcript: string,
    audioData: any[],
    conversationMessages: any[]
  ): Promise<Assessment> {
    const referenceText = extractUserText(conversationMessages)

    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: scenarioId,
        transcript,
        audio_data: audioData,
        reference_text: referenceText,
      }),
    })
    if (!res.ok) throw new Error('Analysis failed')
    return res.json()
  },

  async generateGraphScenario(): Promise<Scenario> {
    const res = await fetch('/api/scenarios/graph', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) throw new Error('Failed to generate Graph scenario')
    return res.json()
  },
}
