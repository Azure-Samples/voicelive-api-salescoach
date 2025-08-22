import { useEffect, useRef, useState, useCallback } from 'react'
import { Message } from '../types'

interface RealtimeOptions {
  agentId?: string | null
  onMessage?: (msg: any) => void
  onAudioDelta?: (delta: string) => void
  onTranscript?: (role: 'user' | 'assistant', text: string) => void
}

export function useRealtime(options: RealtimeOptions) {
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const audioRecording = useRef<any[]>([])
  const conversationRecording = useRef<any[]>([])

  const connect = useCallback(async () => {
    const config = await fetch('/api/config').then(r => r.json())
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(
      `${protocol}//${location.host}${config.ws_endpoint}`
    )

    ws.onopen = () => {
      setConnected(true)
      if (options.agentId) {
        ws.send(
          JSON.stringify({
            type: 'session.update',
            session: { agent_id: options.agentId },
          })
        )
      }
    }

    ws.onmessage = event => {
      const msg = JSON.parse(event.data)
      options.onMessage?.(msg)

      switch (msg.type) {
        case 'response.audio.delta':
          if (msg.delta) {
            options.onAudioDelta?.(msg.delta)
            audioRecording.current.push({
              type: 'assistant',
              data: msg.delta,
              timestamp: new Date().toISOString(),
            })
          }
          break
        case 'conversation.item.input_audio_transcription.completed':
          if (msg.transcript) {
            const message: Message = {
              id: crypto.randomUUID(),
              role: 'user',
              content: msg.transcript,
              timestamp: new Date(),
            }
            setMessages(prev => [...prev, message])
            conversationRecording.current.push({
              role: 'user',
              content: msg.transcript,
            })
            options.onTranscript?.('user', msg.transcript)
          }
          break
        case 'response.audio_transcript.done':
          if (msg.transcript) {
            const message: Message = {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: msg.transcript,
              timestamp: new Date(),
            }
            setMessages(prev => [...prev, message])
            conversationRecording.current.push({
              role: 'assistant',
              content: msg.transcript,
            })
            options.onTranscript?.('assistant', msg.transcript)
          }
          break
      }
    }

    ws.onclose = () => setConnected(false)
    wsRef.current = ws
  }, [options.agentId])

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    conversationRecording.current = []
    audioRecording.current = []
  }, [])

  const getRecordings = useCallback(
    () => ({
      conversation: conversationRecording.current,
      audio: audioRecording.current,
    }),
    []
  )

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  return {
    connected,
    messages,
    send,
    clearMessages,
    getRecordings,
  }
}
