import React, { useCallback, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import ChatWindow from './components/ChatWindow.jsx'
import VoiceRecorder from './components/VoiceRecorder.jsx'
import LlmInput from './components/LlmInput.jsx'
import DocumentUploader from './components/PDFUploader.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import SessionSidebar from './components/SessionSidebar.jsx'
import TTSPlayer from './components/TTSPlayer.jsx'
import {
  setSessions,
  upsertSession,
  removeSession,
  setCurrentSession,
} from './slices/sessionsSlice.js'
import { setMessages, clearMessages } from './slices/chatSlice.js'

const API_BASE = 'http://localhost:8000/api'

export default function App() {
  const dispatch = useDispatch()
  const sessions = useSelector(state => state.sessions.items)
  const currentSessionId = useSelector(state => state.sessions.currentSessionId)

  const loadSession = useCallback(
    async (sessionId) => {
      if (!sessionId) {
        dispatch(clearMessages())
        return
      }
      try {
        const res = await fetch(`${API_BASE}/sessions/${sessionId}`)
        if (!res.ok) throw new Error(`Failed to load session ${sessionId}`)
        const data = await res.json()
        if (data?.session) {
          dispatch(upsertSession(data.session))
        }
        dispatch(setMessages(data?.messages || []))
      } catch (err) {
        console.error(err)
      }
    },
    [dispatch],
  )

  const createSession = useCallback(
    async (title) => {
      try {
        const res = await fetch(`${API_BASE}/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: title ? JSON.stringify({ title }) : '{}',
        })
        if (!res.ok) throw new Error('Failed to create session')
        const data = await res.json()
        if (data?.session) {
          dispatch(upsertSession(data.session))
          dispatch(setCurrentSession(data.session.session_id))
        }
        dispatch(setMessages(data?.messages || []))
        return data?.session || null
      } catch (err) {
        console.error(err)
        return null
      }
    },
    [dispatch],
  )

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`)
      if (!res.ok) throw new Error('Failed to load sessions')
      const data = await res.json()
      dispatch(setSessions(data))
      if (!data?.length) {
        const created = await createSession()
        if (!created) return
        dispatch(setCurrentSession(created.session_id))
        return
      }
      if (!currentSessionId || !data.some(session => session.session_id === currentSessionId)) {
        dispatch(setCurrentSession(data[0].session_id))
      }
    } catch (err) {
      console.error(err)
    }
  }, [createSession, currentSessionId, dispatch])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  useEffect(() => {
    if (!currentSessionId) {
      dispatch(clearMessages())
      return
    }
    loadSession(currentSessionId)
  }, [currentSessionId, loadSession, dispatch])

  const handleSelectSession = useCallback(
    (sessionId) => {
      if (!sessionId || sessionId === currentSessionId) return
      dispatch(setCurrentSession(sessionId))
    },
    [currentSessionId, dispatch],
  )

  const handleDeleteSession = useCallback(
    async (sessionId) => {
      if (!sessionId) return
      try {
        await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' })
      } catch (err) {
        console.error(err)
      }
      const remaining = sessions.filter(session => session.session_id !== sessionId)
      dispatch(removeSession(sessionId))
      const nextId = remaining[0]?.session_id
      if (nextId) {
        dispatch(setCurrentSession(nextId))
      } else {
        const created = await createSession()
        if (created) dispatch(setCurrentSession(created.session_id))
      }
    },
    [createSession, dispatch, sessions],
  )

  const handleRenameSession = useCallback(
    async (sessionId, currentTitle) => {
      if (!sessionId) return
      const title = window.prompt('Rename chat', currentTitle || 'New chat')
      if (title === null) return
      const trimmed = title.trim()
      if (!trimmed) return
      try {
        const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: trimmed }),
        })
        if (!res.ok) throw new Error('Failed to rename session')
        const data = await res.json()
        if (data) {
          dispatch(upsertSession(data))
        }
      } catch (err) {
        console.error(err)
      }
    },
    [dispatch],
  )

  return (
    <div className="app">
      <header className="app-header">
        <h1>NeraAIchat</h1>
        <span className="subtitle">Local voice chat with PDF RAG</span>
      </header>

      <main className="layout">
        <SessionSidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onNewChat={() => createSession()}
          onSelect={handleSelectSession}
          onDelete={handleDeleteSession}
          onRename={handleRenameSession}
        />

        <section className="center">
          <ChatWindow />
          <div className="input-row">
            <LlmInput voiceButton={<VoiceRecorder variant="button" />} />
          </div>
        </section>

        <aside className="right glass-scroll">
          <DocumentUploader />
          <SettingsPanel />
          <TTSPlayer />
        </aside>
      </main>
    </div>
  )
}
