import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { enqueueSpeech, setTtsSpeed, setVoiceMode, shiftSpeech } from '../slices/settingsSlice.js'

const WS_URL = 'ws://localhost:8000/ws/tts'

export default function TTSPlayer() {
  const dispatch = useDispatch()
  const { ttsVoice, voiceMode, ttsSpeed, speechQueue } = useSelector(s => s.settings)
  const [status, setStatus] = useState('')
  const [progress, setProgress] = useState(0)
  const [volume, setVolume] = useState(100)
  const [isPlaying, setIsPlaying] = useState(false)
  const audioRef = useRef(null)
  const codecRef = useRef('audio/ogg; codecs=opus')
  const activeSpeech = useMemo(() => speechQueue?.[0] || null, [speechQueue])

  const synthesize = async (text) => {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(WS_URL)
      const chunks = []
      ws.binaryType = 'arraybuffer'

      ws.onopen = () => {
        ws.send(JSON.stringify({ text, voice: ttsVoice, speed: ttsSpeed }))
        setStatus('Synthesis…')
      }

      ws.onmessage = (ev) => {
        if (typeof ev.data === 'string') {
          try {
            const msg = JSON.parse(ev.data)
            if (msg.type === 'start') {
              codecRef.current = msg.codec === 'audio/wav' ? 'audio/wav' : 'audio/ogg; codecs=opus'
              setStatus(`Receiving ${codecRef.current}…`)
            }
            if (msg.type === 'end') {
              const blob = new Blob(chunks, { type: codecRef.current })
              resolve(blob)
              ws.close()
            }
            if (msg.type === 'error') {
              reject(new Error(msg.message))
              ws.close()
            }
          } catch (err) {
            console.warn('tts parse error', err)
          }
        } else {
          chunks.push(new Uint8Array(ev.data))
        }
      }

      ws.onerror = () => {
        reject(new Error('TTS websocket error'))
        ws.close()
      }

      ws.onclose = () => {}
    })
  }

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    audio.volume = volume / 100
  }, [volume])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    audio.playbackRate = Number(ttsSpeed) || 1
  }, [ttsSpeed])

  useEffect(() => {
    let cancelled = false
    const audio = audioRef.current
    if (!voiceMode || !activeSpeech || !audio) return

    const run = async () => {
      try {
        setProgress(0)
        setIsPlaying(false)
        const blob = await synthesize(activeSpeech.text)
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        audio.src = url
        audio.currentTime = 0
        await audio.play()
      } catch (err) {
        console.error('TTS synth failed', err)
        setStatus(`Error: ${err.message}`)
        dispatch(shiftSpeech())
      }
    }

    run()

    return () => {
      cancelled = true
    }
  }, [activeSpeech, voiceMode, dispatch])

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

  const handleVoiceModeToggle = () => {
    dispatch(setVoiceMode(!voiceMode))
  }

  return (
    <div className="card">
      <div className="card-title">TTS Player</div>
      <div className="settings-group">
        <span className="settings-label">Voice Mode</span>
        <label className="toggle">
          <input type="checkbox" checked={voiceMode} onChange={handleVoiceModeToggle} />
          <span className="toggle-track">
            <span className="toggle-thumb" />
          </span>
        </label>
      </div>
      <div className="settings-group">
        <span className="settings-label">Speed {ttsSpeed.toFixed(2)}×</span>
        <div className="audio-volume">
          <input
            type="range"
            min="0.5"
            max="2"
            step="0.05"
            value={ttsSpeed}
            style={{ '--volume-level': `${((ttsSpeed - 0.5) / 1.5) * 100}%` }}
            onChange={e => dispatch(setTtsSpeed(e.target.value))}
          />
        </div>
      </div>
      <div className="status">{status || (activeSpeech ? `Queue: ${speechQueue.length}` : 'Idle')}</div>
      <div className="audio-player">
        <button onClick={togglePlayback} aria-label={isPlaying ? 'Pause' : 'Play'} disabled={!activeSpeech}>
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
            disabled={!activeSpeech}
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
          dispatch(shiftSpeech())
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />
    </div>
  )
}
