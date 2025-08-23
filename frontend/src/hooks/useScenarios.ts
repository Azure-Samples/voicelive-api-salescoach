/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See LICENSE in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import { useState, useEffect } from 'react'
import { Scenario } from '../types'
import { api } from '../services/api'

export function useScenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getScenarios()
      .then(setScenarios)
      .finally(() => setLoading(false))
  }, [])

  return {
    scenarios,
    selectedScenario,
    setSelectedScenario,
    loading,
  }
}
