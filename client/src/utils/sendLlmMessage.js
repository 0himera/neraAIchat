import { nanoid } from '@reduxjs/toolkit'
import {
  addAssistantMessage,
  addUserMessage,
  updateMessage,
  upsertMessage,
  setMessageStatus,
} from '../slices/chatSlice.js'
import { upsertSession } from '../slices/sessionsSlice.js'

const WS_URL = 'ws://localhost:8000/ws/llm'

export function sendLlmMessage({ dispatch, sessionId, text, systemPrompt, memoryNotes }) {
  const payload = (text || '').trim()
  if (!payload || !sessionId) return null

  const userId = nanoid()
  const assistantId = nanoid()
  dispatch(addUserMessage(payload, userId))

  const ws = new WebSocket(WS_URL)
  let acc = ''

  ws.onopen = () => {
    const system = (systemPrompt || '').trim()
    const memory = (memoryNotes || '').trim()
    ws.send(
      JSON.stringify({
        text: payload,
        session_id: sessionId,
        message_id: userId,
        assistant_id: assistantId,
        system_prompt: system,
        memory_notes: memory,
      }),
    )
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
        console.error('LLM ws error:', data.message)
        dispatch(setMessageStatus({ id: assistantId, status: 'error' }))
      }
      if (data.type === 'done') {
        ws.close()
        dispatch(setMessageStatus({ id: assistantId, status: 'final' }))
      }
    } catch (err) {
      console.warn('Failed to parse LLM ws message', err)
    }
  }

  ws.onerror = (err) => {
    console.error('LLM ws error event', err)
    dispatch(setMessageStatus({ id: assistantId, status: 'error' }))
  }

  return { ws, userId, assistantId }
}
