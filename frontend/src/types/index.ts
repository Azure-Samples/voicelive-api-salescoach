/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See LICENSE in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

export interface Scenario {
  id: string
  name: string
  description: string
  is_graph_scenario?: boolean
  generated_from_graph?: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export interface Assessment {
  ai_assessment?: {
    speaking_tone_style: {
      professional_tone: number
      active_listening: number
      engagement_quality: number
      total: number
    }
    conversation_content: {
      needs_assessment: number
      value_proposition: number
      objection_handling: number
      total: number
    }
    overall_score: number
    strengths: string[]
    improvements: string[]
    specific_feedback?: string
  }
  pronunciation_assessment?: {
    accuracy_score: number
    fluency_score: number
    completeness_score: number
    prosody_score?: number
    pronunciation_score: number
    words?: Array<{
      word: string
      accuracy: number
      error_type: string
    }>
  }
}

export interface AgentConfig {
  agent_id: string
  scenario_id: string
}
export interface AgentConfig {
  agent_id: string
  scenario_id: string
}
