import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { sendLlmMessage } from '../utils/sendLlmMessage.js'

export default function LlmInput({ voiceButton = null }) {
  const [text, setText] = useState('')
  const dispatch = useDispatch()
  const currentSessionId = useSelector(state => state.sessions.currentSessionId)
  const { systemPrompt, memoryNotes } = useSelector(state => state.settings)

  const send = async () => {
    const q = text.trim()
    if (!q) return
    if (!currentSessionId) {
      console.warn('No active session id; cannot send message')
      return
    }
    setText('')
    sendLlmMessage({ dispatch, sessionId: currentSessionId, text: q, systemPrompt, memoryNotes })
  }

  return (
    <div className="input-bar">
      <input
        className="glass-field chat-input"
        placeholder="Type your message..."
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            send()
          }
        }}
      />
      <button type="button" className="glass-input send-button" onClick={send}>
        Send
      </button>
      {voiceButton}
    </div>
  )
}
