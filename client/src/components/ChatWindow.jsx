import React, { useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import ReactMarkdown from 'react-markdown'
import { enqueueSpeech } from '../slices/settingsSlice.js'

export default function ChatWindow() {
  const dispatch = useDispatch()
  const messages = useSelector(s => s.chat.messages)
  const partial = useSelector(s => s.chat.partialAsr)
  const voiceMode = useSelector(s => s.settings.voiceMode)
  const scrollRef = useRef(null)
  const lastSpokenRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, partial])

  useEffect(() => {
    if (!voiceMode) {
      lastSpokenRef.current = null
      return
    }
    const latestFinalAssistant = [...messages]
      .reverse()
      .find(m => m.role === 'assistant' && m.text?.trim() && m.status === 'final')
    if (latestFinalAssistant) {
      lastSpokenRef.current = latestFinalAssistant.id
    }
  }, [voiceMode])

  useEffect(() => {
    if (!voiceMode) return
    const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant' && m.text?.trim())
    if (!lastAssistant) return
    if (lastAssistant.status && lastAssistant.status !== 'final') return
    if (lastSpokenRef.current === lastAssistant.id) return
    const cleanText = lastAssistant.text?.trim()
    if (!cleanText) return
    lastSpokenRef.current = lastAssistant.id
    dispatch(enqueueSpeech({ id: lastAssistant.id, text: cleanText }))
  }, [messages, voiceMode, dispatch])

  return (
    <div className="card chat">
      <div className="card-title">Chat</div>
      <div className="chat-scroll" ref={scrollRef}>
        {messages.map(m => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="role">{m.role}</div>
            <div className="text">
              {m.role === 'assistant' || m.role === 'system' ? (
                <ReactMarkdown>{m.text}</ReactMarkdown>
              ) : (
                m.text
              )}
            </div>
          </div>
        ))}
        {partial && (
          <div className="msg user partial">
            <div className="role">user (partial)</div>
            <div className="text">{partial}</div>
          </div>
        )}
      </div>
    </div>
  )
}
