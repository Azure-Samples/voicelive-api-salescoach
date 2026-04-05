/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See LICENSE in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import { CustomScenario, CustomScenarioData } from '../types'

const STORAGE_KEY = 'voicelive_custom_scenarios'

/**
 * Service for managing custom scenarios in browser localStorage
 */
export const customScenarioService = {
  /**
   * Get all custom scenarios from localStorage
   */
  getAll(): CustomScenario[] {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (!stored) return []
      return JSON.parse(stored) as CustomScenario[]
    } catch (error) {
      console.error('Failed to load custom scenarios:', error)
      return []
    }
  },

  /**
   * Get a specific custom scenario by ID
   */
  get(id: string): CustomScenario | null {
    const scenarios = this.getAll()
    return scenarios.find(s => s.id === id) || null
  },

  /**
   * Save a new custom scenario
   */
  save(
    name: string,
    description: string,
    scenarioData: CustomScenarioData
  ): CustomScenario {
    const scenarios = this.getAll()
    const now = new Date().toISOString()
    const id = `custom-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`

    const newScenario: CustomScenario = {
      id,
      name,
      description,
      is_custom: true,
      scenarioData,
      createdAt: now,
      updatedAt: now,
    }

    scenarios.push(newScenario)
    this._persist(scenarios)
    return newScenario
  },

  /**
   * Update an existing custom scenario
   */
  update(
    id: string,
    updates: Partial<
      Pick<CustomScenario, 'name' | 'description' | 'scenarioData'>
    >
  ): CustomScenario | null {
    const scenarios = this.getAll()
    const index = scenarios.findIndex(s => s.id === id)

    if (index === -1) return null

    const updated: CustomScenario = {
      ...scenarios[index],
      ...updates,
      updatedAt: new Date().toISOString(),
    }

    scenarios[index] = updated
    this._persist(scenarios)
    return updated
  },

  /**
   * Delete a custom scenario
   */
  delete(id: string): boolean {
    const scenarios = this.getAll()
    const filtered = scenarios.filter(s => s.id !== id)

    if (filtered.length === scenarios.length) return false

    this._persist(filtered)
    return true
  },

  /**
   * Export a custom scenario as JSON
   */
  export(id: string): string | null {
    const scenario = this.get(id)
    if (!scenario) return null
    return JSON.stringify(scenario.scenarioData, null, 2)
  },

  /**
   * Import a scenario from JSON data
   */
  import(
    name: string,
    description: string,
    jsonData: string
  ): CustomScenario | null {
    try {
      const scenarioData = JSON.parse(jsonData) as CustomScenarioData

      // Validate required fields
      if (!scenarioData.messages || !Array.isArray(scenarioData.messages)) {
        throw new Error('Invalid scenario format: messages array is required')
      }

      // Set defaults if not provided
      scenarioData.model = scenarioData.model || 'gpt-4o'
      scenarioData.modelParameters = scenarioData.modelParameters || {
        temperature: 0.7,
        max_tokens: 2000,
      }

      return this.save(name, description, scenarioData)
    } catch (error) {
      console.error('Failed to import scenario:', error)
      return null
    }
  },

  /**
   * Create a default template for new scenarios
   */
  createTemplate(): CustomScenarioData {
    return {
      name: 'New Custom Scenario',
      description: 'A custom role-play scenario',
      model: 'gpt-4o',
      modelParameters: {
        temperature: 0.7,
        max_tokens: 2000,
      },
      messages: [
        {
          role: 'system',
          content: `You are a professional playing a specific role in a business scenario.

BEHAVIORAL GUIDELINES:
- Show genuine interest but maintain professional demeanor
- Ask clarifying questions when information seems unclear
- React appropriately to proposals and suggestions
- Use natural conversational patterns

YOUR CHARACTER PROFILE:
- [Define the character's background and experience]
- [Define their goals and motivations]
- [Define their concerns and challenges]

KEY TOPICS TO ADDRESS:
1. [Topic 1]
2. [Topic 2]
3. [Topic 3]

Respond naturally as this character would, maintaining a professional tone.`,
        },
        {
          role: 'user',
          content: '{{user_message}}',
        },
      ],
    }
  },

  /**
   * Internal method to persist scenarios to localStorage
   */
  _persist(scenarios: CustomScenario[]): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(scenarios))
    } catch (error) {
      console.error('Failed to persist custom scenarios:', error)
      throw new Error('Failed to save scenario. Storage may be full.')
    }
  },
}
