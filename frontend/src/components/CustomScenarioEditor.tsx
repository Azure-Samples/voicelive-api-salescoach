/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See LICENSE in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  DialogTrigger,
  Field,
  Input,
  Text,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import {
  Add24Regular,
  ArrowDownload24Regular,
  ArrowUpload24Regular,
  Delete24Regular,
  Edit24Regular,
} from '@fluentui/react-icons'
import { useRef, useState } from 'react'
import { customScenarioService } from '../services/customScenarios'
import { CustomScenario, CustomScenarioData } from '../types'

const useStyles = makeStyles({
  dialogContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
  },
  textarea: {
    minHeight: '200px',
    fontFamily: 'monospace',
    fontSize: '12px',
  },
  buttonGroup: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
  },
  iconButton: {
    minWidth: 'auto',
  },
  errorText: {
    color: tokens.colorPaletteRedForeground1,
    fontSize: '12px',
  },
  helpText: {
    color: tokens.colorNeutralForeground3,
    fontSize: '12px',
  },
})

interface CustomScenarioEditorProps {
  scenario?: CustomScenario | null
  onSave: (
    name: string,
    description: string,
    scenarioData: CustomScenarioData
  ) => void
  onDelete?: (id: string) => void
  trigger?: React.ReactNode
}

export function CustomScenarioEditor({
  scenario,
  onSave,
  onDelete,
  trigger,
}: CustomScenarioEditorProps) {
  const styles = useStyles()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(scenario?.name || '')
  const [description, setDescription] = useState(scenario?.description || '')
  const [systemPrompt, setSystemPrompt] = useState(
    scenario?.scenarioData?.messages?.[0]?.content || ''
  )
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isEditing = !!scenario

  const handleOpen = () => {
    if (scenario) {
      setName(scenario.name)
      setDescription(scenario.description)
      setSystemPrompt(scenario.scenarioData.messages[0]?.content || '')
    } else {
      const template = customScenarioService.createTemplate()
      setName('')
      setDescription('')
      setSystemPrompt(template.messages[0]?.content || '')
    }
    setError(null)
    setOpen(true)
  }

  const handleSave = () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (!systemPrompt.trim()) {
      setError('System prompt is required')
      return
    }

    const scenarioData: CustomScenarioData = {
      name: name.trim(),
      description: description.trim(),
      model: 'gpt-4o',
      modelParameters: {
        temperature: 0.7,
        max_tokens: 2000,
      },
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: '{{user_message}}' },
      ],
    }

    onSave(name.trim(), description.trim(), scenarioData)
    setOpen(false)
  }

  const handleDelete = () => {
    if (scenario && onDelete) {
      onDelete(scenario.id)
      setOpen(false)
    }
  }

  const handleExport = () => {
    if (!scenario) return
    const json = customScenarioService.export(scenario.id)
    if (json) {
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${scenario.name.replace(/\s+/g, '-').toLowerCase()}.json`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = e => {
      try {
        const content = e.target?.result as string
        const data = JSON.parse(content) as CustomScenarioData

        setName(data.name || file.name.replace('.json', ''))
        setDescription(data.description || '')
        setSystemPrompt(data.messages?.[0]?.content || '')
        setError(null)
      } catch {
        setError('Failed to parse JSON file')
      }
    }
    reader.readAsText(file)

    // Reset input so same file can be selected again
    event.target.value = ''
  }

  const defaultTrigger = isEditing ? (
    <Button
      appearance="subtle"
      icon={<Edit24Regular />}
      className={styles.iconButton}
      title="Edit scenario"
    />
  ) : (
    <Button appearance="primary" icon={<Add24Regular />}>
      Create Custom Scenario
    </Button>
  )

  return (
    <Dialog open={open} onOpenChange={(_, data) => setOpen(data.open)}>
      <DialogTrigger disableButtonEnhancement>
        <span onClick={handleOpen}>{trigger || defaultTrigger}</span>
      </DialogTrigger>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>
            {isEditing ? 'Edit Custom Scenario' : 'Create Custom Scenario'}
          </DialogTitle>
          <DialogContent className={styles.dialogContent}>
            <Field label="Scenario Name" required>
              <Input
                value={name}
                onChange={(_, data) => setName(data.value)}
                placeholder="e.g., Product Demo Presentation"
              />
            </Field>

            <Field label="Description">
              <Input
                value={description}
                onChange={(_, data) => setDescription(data.value)}
                placeholder="Brief description of the scenario"
              />
            </Field>

            <Field
              label="System Prompt"
              required
              hint="Define the AI character's role, behavior, and conversation context"
            >
              <Textarea
                value={systemPrompt}
                onChange={(_, data) => setSystemPrompt(data.value)}
                className={styles.textarea}
                placeholder="You are a professional playing a specific role..."
                resize="vertical"
              />
            </Field>

            <Text className={styles.helpText}>
              The system prompt defines how the AI will behave during the
              role-play. Include character background, behavioral guidelines,
              and key topics to address.
            </Text>

            {error && <Text className={styles.errorText}>{error}</Text>}

            <div className={styles.buttonGroup}>
              <Button
                appearance="subtle"
                icon={<ArrowUpload24Regular />}
                onClick={handleImportClick}
              >
                Import JSON
              </Button>
              {isEditing && (
                <Button
                  appearance="subtle"
                  icon={<ArrowDownload24Regular />}
                  onClick={handleExport}
                >
                  Export JSON
                </Button>
              )}
            </div>

            <input
              type="file"
              ref={fileInputRef}
              accept=".json"
              style={{ display: 'none' }}
              onChange={handleFileImport}
            />
          </DialogContent>
          <DialogActions>
            {isEditing && onDelete && (
              <Button
                appearance="subtle"
                icon={<Delete24Regular />}
                onClick={handleDelete}
                style={{ marginRight: 'auto' }}
              >
                Delete
              </Button>
            )}
            <DialogTrigger disableButtonEnhancement>
              <Button appearance="secondary">Cancel</Button>
            </DialogTrigger>
            <Button appearance="primary" onClick={handleSave}>
              {isEditing ? 'Save Changes' : 'Create Scenario'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
