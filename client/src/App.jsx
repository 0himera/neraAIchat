import React from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import VoiceRecorder from './components/VoiceRecorder.jsx'
import LlmInput from './components/LlmInput.jsx'
import PDFUploader from './components/PDFUploader.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import TTSPlayer from './components/TTSPlayer.jsx'

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>NeraAIchat</h1>
        <span className="subtitle">Local voice chat with PDF RAG</span>
      </header>

      <main className="layout">
        <section className="left">
          <ChatWindow />
          <div className="input-row">
            <VoiceRecorder />
            <LlmInput />
          </div>
        </section>
        <aside className="right">
          <PDFUploader />
          <SettingsPanel />
          <TTSPlayer />
        </aside>
      </main>
    </div>
  )
}
