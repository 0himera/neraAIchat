import React, { useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { addUserMessage, addAssistantMessage, replaceLastAssistant } from '../slices/chatSlice.js'

const WS_URL = 'ws://localhost:8000/ws/llm'

export default function LlmInput() {
  const [text, setText] = useState('')
  const dispatch = useDispatch()
  const wsRef = useRef(null)

  const send = async () => {
    const q = text.trim()
    if (!q) return
    setText('')
    dispatch(addUserMessage(q))

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    let acc = ''

    ws.onopen = () => {
      ws.send(JSON.stringify({ text: q }))
      // create placeholder assistant message
      dispatch(addAssistantMessage(''))
    }
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data.type === 'token') {
          acc += data.text
          dispatch(replaceLastAssistant(acc))
        }
        if (data.type === 'done') ws.close()
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
