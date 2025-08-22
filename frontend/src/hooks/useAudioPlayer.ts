import { useRef, useCallback } from 'react'

export function useAudioPlayer() {
  const audioCtxRef = useRef<AudioContext | null>(null)
  const nextPlayTimeRef = useRef(0)

  const initAudio = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext({ sampleRate: 24000 })
    }
    return audioCtxRef.current
  }, [])

  const playAudio = useCallback(
    (base64: string) => {
      const audioCtx = initAudio()
      audioCtx.resume?.()

      const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
      const int16 = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(int16.length)

      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768
      }

      const buffer = audioCtx.createBuffer(1, float32.length, 24000)
      buffer.getChannelData(0).set(float32)

      const src = audioCtx.createBufferSource()
      src.buffer = buffer
      src.connect(audioCtx.destination)

      nextPlayTimeRef.current = Math.max(
        nextPlayTimeRef.current,
        audioCtx.currentTime
      )
      src.start(nextPlayTimeRef.current)
      nextPlayTimeRef.current += buffer.duration
    },
    [initAudio]
  )

  return { playAudio }
}
