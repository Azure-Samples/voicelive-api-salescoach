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
