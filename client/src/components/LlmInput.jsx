import React, { useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { nanoid } from '@reduxjs/toolkit'
import {
  addUserMessage,
  addAssistantMessage,
  updateMessage,
  upsertMessage,
} from '../slices/chatSlice.js'
import { upsertSession } from '../slices/sessionsSlice.js'

const WS_URL = 'ws://localhost:8000/ws/llm'

export default function LlmInput() {
  const [text, setText] = useState('')
  const dispatch = useDispatch()
  const wsRef = useRef(null)
  const currentSessionId = useSelector(state => state.sessions.currentSessionId)

  const send = async () => {
    const q = text.trim()
    if (!q) return
    if (!currentSessionId) {
      console.warn('No active session id; cannot send message')
      return
    }
    setText('')
    const userId = nanoid()
    const assistantId = nanoid()
    dispatch(addUserMessage(q, userId))

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    let acc = ''

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          text: q,
          session_id: currentSessionId,
          message_id: userId,
          assistant_id: assistantId,
        }),
      )
      // create placeholder assistant message
      dispatch(addAssistantMessage('', assistantId))
    }
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data.type === 'token') {
          acc += data.text
          dispatch(updateMessage({ id: assistantId, text: acc }))
        }
        if (data.type === 'session_update') {
          if (data.session) {
            dispatch(upsertSession(data.session))
          }
          if (data.message) {
            dispatch(upsertMessage(data.message))
          }
        }
        if (data.type === 'error') {
          console.error('ws error', data.message)
        }
        if (data.type === 'done') {
          ws.close()
        }
      } catch {}
    }
  }

  return (
    <div className="row grow">
      <input
        className="input"
        placeholder="Type your message..."
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && send()}
      />
      <button className="btn" onClick={send}>Send</button>
    </div>
  )
}
