/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See LICENSE in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import { useCallback, useEffect, useRef } from 'react'

export function useWebRTC(onSendOffer: (sdp: string) => void) {
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const audioElementsRef = useRef<HTMLAudioElement[]>([])

  const setupWebRTC = useCallback(
    async (iceServers: any, username?: string, password?: string) => {
      // Clear any pending ICE gathering timeout from a previous connection
      if (gatheringTimeoutRef.current) {
        clearTimeout(gatheringTimeoutRef.current)
        gatheringTimeoutRef.current = null
      }

      // Close existing peer connection before creating a new one
      if (pcRef.current) {
        pcRef.current.close()
        pcRef.current = null
      }

      // Remove previously injected audio elements
      audioElementsRef.current.forEach(el => {
        el.srcObject = null
        el.remove()
      })
      audioElementsRef.current = []

      let servers = Array.isArray(iceServers)
        ? iceServers
        : [{ urls: iceServers }]
      if (username && password) {
        servers = servers.map(s => ({
          urls: typeof s === 'string' ? s : s.urls,
          username,
          credential: password,
          credentialType: 'password' as const,
        }))
      }

      const pc = new RTCPeerConnection({
        iceServers: servers,
        bundlePolicy: 'max-bundle',
      })

      let offerSent = false
      const sendOfferOnce = () => {
        if (offerSent || !pc.localDescription) return
        offerSent = true
        const sdp = btoa(
          JSON.stringify({
            type: 'offer',
            sdp: pc.localDescription.sdp,
          })
        )
        onSendOffer(sdp)
      }

      pc.onicecandidate = e => {
        if (!e.candidate) {
          sendOfferOnce()
        }
      }

      // Fallback: send offer after 3s even if ICE gathering hasn't completed.
      // Avoids ~30s delays when TURN servers are slow on reconnection.
      gatheringTimeoutRef.current = setTimeout(sendOfferOnce, 3000)

      pc.ontrack = e => {
        if (e.track.kind === 'video' && videoRef.current) {
          videoRef.current.srcObject = e.streams[0]
          videoRef.current.play()
        } else if (e.track.kind === 'audio') {
          const audio = document.createElement('audio')
          audio.srcObject = e.streams[0]
          audio.autoplay = true
          audio.style.display = 'none'
          document.body.appendChild(audio)
          audioElementsRef.current.push(audio)
        }
      }

      pc.addTransceiver('video', { direction: 'recvonly' })
      pc.addTransceiver('audio', { direction: 'recvonly' })

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      pcRef.current = pc
    },
    [onSendOffer]
  )

  const handleAnswer = useCallback(async (msg: any) => {
    if (!pcRef.current || pcRef.current.signalingState !== 'have-local-offer')
      return

    const sdp = msg.server_sdp
      ? JSON.parse(atob(msg.server_sdp)).sdp
      : msg.sdp || msg.answer

    if (sdp) {
      await pcRef.current.setRemoteDescription({ type: 'answer', sdp })
    }
  }, [])

  const gatheringTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (gatheringTimeoutRef.current) clearTimeout(gatheringTimeoutRef.current)
      pcRef.current?.close()
      audioElementsRef.current.forEach(el => {
        el.srcObject = null
        el.remove()
      })
      audioElementsRef.current = []
    }
  }, [])

  return {
    setupWebRTC,
    handleAnswer,
    videoRef,
  }
}
