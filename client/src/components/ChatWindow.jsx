import React from 'react'
import { useSelector } from 'react-redux'

export default function ChatWindow() {
  const messages = useSelector(s => s.chat.messages)
  const partial = useSelector(s => s.chat.partialAsr)

  return (
    <div className="card chat">
      <div className="card-title">Chat</div>
      <div className="chat-scroll">
        {messages.map(m => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="role">{m.role}</div>
            <div className="text">{m.text}</div>
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
