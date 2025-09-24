import React, { useEffect, useRef } from 'react'
import { useSelector } from 'react-redux'
import ReactMarkdown from 'react-markdown'

export default function ChatWindow() {
  const messages = useSelector(s => s.chat.messages)
  const partial = useSelector(s => s.chat.partialAsr)
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, partial])

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
