import React, { useRef, useState } from 'react'
import { useSelector } from 'react-redux'

const WS_URL = 'ws://localhost:8000/ws/tts'

export default function TTSPlayer() {
  const [text, setText] = useState('Hello from Piper!')
  const [status, setStatus] = useState('')
  const audioRef = useRef(null)
  const ttsVoice = useSelector(s => s.settings.ttsVoice)
  const codecRef = useRef('audio/ogg; codecs=opus')

  const speak = async () => {
    if (!text.trim()) return
    setStatus('Synthesis...')
    const ws = new WebSocket(WS_URL)
    const chunks = []

    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      ws.send(JSON.stringify({ text, voice: ttsVoice }))
    }

    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'start') {
            // Server may send codec: 'ogg/opus' or 'audio/wav'
            codecRef.current = msg.codec === 'audio/wav' ? 'audio/wav' : 'audio/ogg; codecs=opus'
            setStatus(`Receiving ${codecRef.current}...`)
          }
          if (msg.type === 'end') {
            const blob = new Blob(chunks, { type: codecRef.current })
            const url = URL.createObjectURL(blob)
            const audio = audioRef.current
            audio.src = url
            audio.play()
            setStatus('Done')
            ws.close()
          }
          if (msg.type === 'error') {
            setStatus('Error: ' + msg.message)
          }
        } catch {
          // text but not JSON
        }
      } else {
        chunks.push(new Uint8Array(ev.data))
      }
    }

    ws.onerror = () => setStatus('WS error')
    ws.onclose = () => {}
  }

  return (
    <div className="card">
      <div className="card-title">TTS Player</div>
      <div className="row">
        <input className="input" value={text} onChange={e => setText(e.target.value)} />
        <button className="btn" onClick={speak}>Speak</button>
      </div>
      <div className="status">{status}</div>
      <audio ref={audioRef} controls />
    </div>
  )
}
