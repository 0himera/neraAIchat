import React, { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { setPartialAsr } from '../slices/chatSlice.js'
import { sendLlmMessage } from '../utils/sendLlmMessage.js'

const WS_URL = 'ws://localhost:8000/ws/asr'

export default function VoiceRecorder({ variant = 'card' }) {
  const dispatch = useDispatch()
  const chunkMs = useSelector(s => s.settings.chunkMs)
  const currentSessionId = useSelector(s => s.sessions.currentSessionId)
  const { systemPrompt, memoryNotes } = useSelector(s => s.settings)
  const [recording, setRecording] = useState(false)
  const [status, setStatus] = useState('')
  const wsRef = useRef(null)
  const mrRef = useRef(null)
  const streamRef = useRef(null)
  const llmWsRef = useRef(null)

  useEffect(() => {
    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close()
      }
      if (llmWsRef.current && llmWsRef.current.readyState === WebSocket.OPEN) {
        llmWsRef.current.close()
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      }
    }
  }, [])

  const start = async () => {
    if (recording) return
    if (!currentSessionId) {
      setStatus('No active session selected')
      return
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mr = new MediaRecorder(stream, { mimeType: 'audio/ogg; codecs=opus' })
    mrRef.current = mr
    streamRef.current = stream

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data.type === 'partial') dispatch(setPartialAsr(data.text))
        if (data.type === 'final') {
          dispatch(setPartialAsr(''))
          const finalText = (data.text || '').trim()
          if (finalText) {
            setStatus('Sending to assistant…')
            const result = sendLlmMessage({
              dispatch,
              sessionId: currentSessionId,
              text: finalText,
              systemPrompt,
              memoryNotes,
            })
            llmWsRef.current = result?.ws || null
          } else {
            setStatus('No speech detected')
          }
          ws.close()
          setStatus('Done')
        }
        if (data.type === 'error') {
          setStatus(`ASR error: ${data.message}`)
        }
      } catch {}
    }

    ws.onerror = () => {
      setStatus('ASR websocket error')
    }

    ws.onclose = () => {
      setRecording(false)
    }

    mr.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        e.data.arrayBuffer().then(buf => {
          if (ws.readyState === WebSocket.OPEN) ws.send(buf)
        })
      }
    }

    mr.onstop = () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      }
    }

    mr.start(chunkMs)
    setRecording(true)
    setStatus('Recording…')
  }

  const stop = () => {
    if (!recording) return
    if (mrRef.current && mrRef.current.state !== 'inactive') mrRef.current.stop()
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send('final')
    } else {
      setRecording(false)
    }
    setStatus('Processing…')
  }

  if (variant === 'button') {
    return (
      <button
        type="button"
        className={`glass-input voice-button ${recording ? 'active' : ''}`}
        onClick={recording ? stop : start}
        title={status || (recording ? 'Recording…' : 'Start voice message')}
      >
        {recording ? 'Stop mic' : 'Voice'}
      </button>
    )
  }

  return (
    <div className="card">
      <div className="card-title">Voice</div>
      <div className="row">
        <button className={recording ? 'btn danger' : 'btn'} onClick={recording ? stop : start}>
          {recording ? 'Stop' : 'Record'}
        </button>
        <span className="hint">Opus 48kHz streaming over WS</span>
      </div>
      {status && <div className="status">{status}</div>}
    </div>
  )
}
