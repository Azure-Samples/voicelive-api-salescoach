import React, { useState, useCallback } from 'react'
import {
  Dialog,
  DialogSurface,
  DialogBody,
  Spinner,
  Text,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import { ScenarioList } from '../components/ScenarioList'
import { VideoPanel } from '../components/VideoPanel'
import { ChatPanel } from '../components/ChatPanel'
import { AssessmentPanel } from '../components/AssessmentPanel'
import { useScenarios } from '../hooks/useScenarios'
import { useRealtime } from '../hooks/useRealtime'
import { useWebRTC } from '../hooks/useWebRTC'
import { useRecorder } from '../hooks/useRecorder'
import { useAudioPlayer } from '../hooks/useAudioPlayer'
import { api } from '../services/api'
import { Assessment } from '../types'

const useStyles = makeStyles({
  container: {
    width: '100%',
    height: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: tokens.colorNeutralBackground3,
    padding: tokens.spacingVerticalL,
  },
  mainLayout: {
    width: '95%',
    maxWidth: '1400px',
    height: '90vh',
    display: 'flex',
    gap: tokens.spacingHorizontalL,
  },
  setupDialog: {
    maxWidth: '600px',
    width: '90vw',
  },
  loadingContent: {
    gridColumn: '1 / -1',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    width: '100%',
  },
})

export default function App() {
  const styles = useStyles()
  const [showSetup, setShowSetup] = useState(true)
  const [showLoading, setShowLoading] = useState(false)
  const [showAssessment, setShowAssessment] = useState(false)
  const [currentAgent, setCurrentAgent] = useState<string | null>(null)
  const [assessment, setAssessment] = useState<Assessment | null>(null)

  const { scenarios, selectedScenario, setSelectedScenario, loading } =
    useScenarios()
  const { playAudio } = useAudioPlayer()
  const activeScenario = scenarios.find(s => s.id === selectedScenario) || null

  const handleWebRTCMessage = useCallback((msg: any) => {
    if (msg.type === 'session.updated') {
      const session = msg.session
      const servers =
        session?.avatar?.ice_servers ||
        session?.rtc?.ice_servers ||
        session?.ice_servers
      const username =
        session?.avatar?.username ||
        session?.avatar?.ice_username ||
        session?.rtc?.ice_username ||
        session?.ice_username
      const credential =
        session?.avatar?.credential ||
        session?.avatar?.ice_credential ||
        session?.rtc?.ice_credential ||
        session?.ice_credential

      if (servers) {
        setupWebRTC(servers, username, credential)
      }
    } else if (
      (msg.server_sdp || msg.sdp || msg.answer) &&
      msg.type !== 'session.update'
    ) {
      handleAnswer(msg)
    }
  }, [])

  const { connected, messages, send, clearMessages, getRecordings } =
    useRealtime({
      agentId: currentAgent,
      onMessage: handleWebRTCMessage,
      onAudioDelta: playAudio,
    })

  const sendOffer = useCallback(
    (sdp: string) => {
      send({ type: 'session.avatar.connect', client_sdp: sdp })
    },
    [send]
  )

  const { setupWebRTC, handleAnswer, videoRef } = useWebRTC(sendOffer)

  const sendAudioChunk = useCallback(
    (base64: string) => {
      send({ type: 'input_audio_buffer.append', audio: base64 })
    },
    [send]
  )

  const { recording, toggleRecording, getAudioRecording } =
    useRecorder(sendAudioChunk)

  const handleStart = async () => {
    if (!selectedScenario) return

    try {
      const { agent_id } = await api.createAgent(selectedScenario)
      setCurrentAgent(agent_id)
      setShowSetup(false)
    } catch (error) {
      console.error('Failed to create agent:', error)
    }
  }

  const handleAnalyze = async () => {
    if (!selectedScenario) return

    const recordings = getRecordings()
    const audioData = getAudioRecording()

    if (!recordings.conversation.length) return

    setShowLoading(true)

    try {
      const transcript = recordings.conversation
        .map((m: any) => `${m.role}: ${m.content}`)
        .join('\n')

      const result = await api.analyzeConversation(
        selectedScenario,
        transcript,
        [...audioData, ...recordings.audio]
      )

      setAssessment(result)
      setShowAssessment(true)
    } catch (error) {
      console.error('Analysis failed:', error)
    } finally {
      setShowLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <Dialog
        open={showSetup}
        onOpenChange={(_, data) => setShowSetup(data.open)}
      >
        <DialogSurface className={styles.setupDialog}>
          <DialogBody>
            {loading ? (
              <Spinner label="Loading scenarios..." />
            ) : (
              <ScenarioList
                scenarios={scenarios}
                selectedScenario={selectedScenario}
                onSelect={setSelectedScenario}
                onStart={handleStart}
              />
            )}
          </DialogBody>
        </DialogSurface>
      </Dialog>

      <Dialog open={showLoading}>
        <DialogSurface>
          <DialogBody>
            <div className={styles.loadingContent}>
              <Spinner size="large" />
              <Text
                size={400}
                weight="semibold"
                block
                style={{ marginTop: tokens.spacingVerticalL }}
              >
                Analyzing Performance...
              </Text>
              <Text
                size={200}
                block
                style={{ marginTop: tokens.spacingVerticalS }}
              >
                This may take up to 30 seconds
              </Text>
            </div>
          </DialogBody>
        </DialogSurface>
      </Dialog>

      <AssessmentPanel
        open={showAssessment}
        assessment={assessment}
        onClose={() => setShowAssessment(false)}
      />

      {!showSetup && (
        <div className={styles.mainLayout}>
          <VideoPanel videoRef={videoRef} />
          <ChatPanel
            messages={messages}
            recording={recording}
            connected={connected}
            canAnalyze={messages.length > 0}
            onToggleRecording={toggleRecording}
            onClear={clearMessages}
            onAnalyze={handleAnalyze}
            scenario={activeScenario}
          />
        </div>
      )}
    </div>
  )
}
