import React, { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'

const WS_URL = 'ws://localhost:8000/ws/tts'

export default function TTSPlayer() {
  const [text, setText] = useState('Hello from Piper!')
  const [status, setStatus] = useState('')
  const [progress, setProgress] = useState(0)
  const [volume, setVolume] = useState(100)
  const [isPlaying, setIsPlaying] = useState(false)
  const audioRef = useRef(null)
  const ttsVoice = useSelector(s => s.settings.ttsVoice)
  const codecRef = useRef('audio/ogg; codecs=opus')

  const speak = async () => {
    if (!text.trim()) return
    setStatus('Synthesis...')
    setProgress(0)
    setIsPlaying(false)
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
            audio.currentTime = 0
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

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    audio.volume = volume / 100
  }, [volume])

  const handleTimeUpdate = () => {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    const pct = (audio.currentTime / audio.duration) * 100
    setProgress(Math.min(100, Math.max(0, pct)))
  }

  const handleSeek = (value) => {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    const clamped = Math.min(100, Math.max(0, Number(value)))
    audio.currentTime = (audio.duration * clamped) / 100
    setProgress(clamped)
  }

  const togglePlayback = () => {
    const audio = audioRef.current
    if (!audio) return
    if (audio.paused) {
      audio.play()
    } else {
      audio.pause()
    }
  }

  return (
    <div className="card">
      <div className="card-title">TTS Player</div>
      <div className="settings-group">
        <span className="settings-label">Prompt</span>
      </div>
      <div className="row">
        <input className="glass-field" value={text} onChange={e => setText(e.target.value)} />
        <button className="glass-input" onClick={speak}>Speak</button>
      </div>
      <div className="status">{status}</div>
      <div className="audio-player">
        <button onClick={togglePlayback} aria-label={isPlaying ? 'Pause' : 'Play'}>
          {isPlaying ? '❚❚' : '▶'}
        </button>
        <div className="audio-slider">
          <input
            type="range"
            min="0"
            max="100"
            value={progress}
            style={{ '--progress': `${progress}%` }}
            onChange={e => handleSeek(e.target.value)}
          />
        </div>
        <div className="audio-volume">
          <input
            type="range"
            min="0"
            max="100"
            value={volume}
            style={{ '--volume-level': `${volume}%` }}
            onChange={e => setVolume(Number(e.target.value))}
          />
        </div>
      </div>
      <audio
        ref={audioRef}
        className="audio-hidden"
        controls
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleTimeUpdate}
        onEnded={() => {
          setIsPlaying(false)
          setProgress(100)
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />
    </div>
  )
}
