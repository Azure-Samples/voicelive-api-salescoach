import { useRef, useState, useCallback } from 'react'

const audioProcessorCode = `
class AudioRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.recording = false
    this.buffer = []
    this.port.onmessage = e => {
      if (e.data.command === 'START') this.recording = true
      else if (e.data.command === 'STOP') {
        this.recording = false
        if (this.buffer.length) this.sendBuffer()
      }
    }
  }
  sendBuffer() {
    if (this.buffer.length) {
      this.port.postMessage({
        eventType: 'audio',
        audioData: new Float32Array(this.buffer)
      })
      this.buffer = []
    }
  }
  process(inputs) {
    if (inputs[0]?.length && this.recording) {
      this.buffer.push(...inputs[0][0])
      if (this.buffer.length >= 2400) this.sendBuffer()
    }
    return true
  }
}
registerProcessor('audio-recorder', AudioRecorderProcessor)
`

export function useRecorder(onAudioChunk: (base64: string) => void) {
  const [recording, setRecording] = useState(false)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const audioRecording = useRef<any[]>([])

  const initAudio = useCallback(async () => {
    if (audioCtxRef.current) return

    const audioCtx = new AudioContext({ sampleRate: 24000 })
    const blob = new Blob([audioProcessorCode], {
      type: 'application/javascript',
    })
    const url = URL.createObjectURL(blob)
    await audioCtx.audioWorklet.addModule(url)
    URL.revokeObjectURL(url)
    audioCtxRef.current = audioCtx
  }, [])

  const startRecording = useCallback(async () => {
    await initAudio()
    const audioCtx = audioCtxRef.current!

    if (audioCtx.state === 'suspended') {
      await audioCtx.resume()
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 24000,
        echoCancellation: true,
      },
    })

    const source = audioCtx.createMediaStreamSource(stream)
    const worklet = new AudioWorkletNode(audioCtx, 'audio-recorder')

    worklet.port.onmessage = e => {
      if (e.data.eventType === 'audio') {
        const float32 = e.data.audioData
        const int16 = new Int16Array(float32.length)
        for (let i = 0; i < float32.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32767))
        }
        const base64 = btoa(
          String.fromCharCode(...new Uint8Array(int16.buffer))
        )
        audioRecording.current.push({
          type: 'user',
          data: base64,
          timestamp: new Date().toISOString(),
        })
        onAudioChunk(base64)
      }
    }

    source.connect(worklet)
    worklet.connect(audioCtx.destination)
    worklet.port.postMessage({ command: 'START' })

    workletRef.current = worklet
    setRecording(true)
  }, [onAudioChunk, initAudio])

  const stopRecording = useCallback(() => {
    if (workletRef.current) {
      workletRef.current.port.postMessage({ command: 'STOP' })
      workletRef.current.disconnect()
      workletRef.current = null
    }
    setRecording(false)
  }, [])

  const toggleRecording = useCallback(async () => {
    if (recording) {
      stopRecording()
    } else {
      await startRecording()
    }
  }, [recording, startRecording, stopRecording])

  const getAudioRecording = useCallback(() => audioRecording.current, [])

  return {
    recording,
    toggleRecording,
    getAudioRecording,
  }
}
