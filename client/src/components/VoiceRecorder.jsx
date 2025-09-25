import React, { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { setPartialAsr } from '../slices/chatSlice.js'

const WS_URL = 'ws://localhost:8000/ws/asr'

export default function VoiceRecorder({ variant = 'card' }) {
  const dispatch = useDispatch()
  const chunkMs = useSelector(s => s.settings.chunkMs)
  const [recording, setRecording] = useState(false)
  const wsRef = useRef(null)
  const mrRef = useRef(null)

  useEffect(() => {
    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close()
      }
    }
  }, [])

  const start = async () => {
    if (recording) return
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mr = new MediaRecorder(stream, { mimeType: 'audio/ogg; codecs=opus' })
    mrRef.current = mr

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data.type === 'partial') dispatch(setPartialAsr(data.text))
        if (data.type === 'final') dispatch(setPartialAsr(''))
      } catch {}
    }

    mr.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        e.data.arrayBuffer().then(buf => {
          if (ws.readyState === WebSocket.OPEN) ws.send(buf)
        })
      }
    }

    mr.start(chunkMs)
    setRecording(true)
  }

  const stop = () => {
    if (!recording) return
    if (mrRef.current && mrRef.current.state !== 'inactive') mrRef.current.stop()
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.send('final')
    setRecording(false)
  }

  if (variant === 'button') {
    return (
      <button
        type="button"
        className={`glass-input voice-button ${recording ? 'active' : ''}`}
        onClick={recording ? stop : start}
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
    </div>
  )
}
