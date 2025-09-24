import React from 'react'

export default function SessionSidebar({
  sessions,
  currentSessionId,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
}) {
  return (
    <aside className="sidebar">
      <div className="card sidebar-header">
        <button className="btn primary full" onClick={() => onNewChat?.()}>
          + New chat
        </button>
      </div>
      <div className="card session-list">
        {sessions.length === 0 && (
          <div className="session-empty">No chats yet. Create one to get started.</div>
        )}
        {sessions.map((session) => {
          const active = session.session_id === currentSessionId
          return (
            <div
              key={session.session_id}
              className={`session-item ${active ? 'active' : ''}`}
              onClick={() => onSelect?.(session.session_id)}
            >
              <div className="session-main">
                <div className="session-title">{session.title || 'New chat'}</div>
                {session.last_message_preview && (
                  <div className="session-preview">{session.last_message_preview}</div>
                )}
              </div>
              <div className="session-actions">
                <button
                  className="icon"
                  title="Rename"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRename?.(session.session_id, session.title)
                  }}
                >
                  ✎
                </button>
                <button
                  className="icon danger"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete?.(session.session_id)
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </aside>
  )
}
