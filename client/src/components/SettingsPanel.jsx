import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { setEnableRag, setTtsVoice, setChunkMs } from '../slices/settingsSlice.js'
import PromptSettingsModal from './PromptSettingsModal.jsx'

export default function SettingsPanel() {
  const dispatch = useDispatch()
  const { enableRag, ttsVoice, chunkMs } = useSelector(s => s.settings)
  const [showPromptModal, setShowPromptModal] = useState(false)

  return (
    <div className="card">
      <div className="card-title">Settings</div>

      <div className="settings-group">
        <span className="settings-label">Enable RAG</span>
        <label className="toggle">
          <input type="checkbox" checked={enableRag} onChange={e => dispatch(setEnableRag(e.target.checked))} />
          <span className="toggle-track">
            <span className="toggle-thumb" />
          </span>
        </label>
      </div>

      <div className="settings-group">
        <span className="settings-label">Voice</span>
        <select className="glass-select" value={ttsVoice} onChange={e => dispatch(setTtsVoice(e.target.value))}>
          <option value="en">English</option>
          <option value="ru">Russian</option>
        </select>
      </div>

      <div className="settings-group">
        <span className="settings-label">Chunk (ms)</span>
        <input
          className="glass-field"
          type="number"
          min={100}
          max={1000}
          step={50}
          value={chunkMs}
          onChange={e => dispatch(setChunkMs(e.target.value))}
        />
      </div>

      <button type="button" className="glass-input full" onClick={() => setShowPromptModal(true)}>
        System Prompts & Memory
      </button>

      <PromptSettingsModal open={showPromptModal} onClose={() => setShowPromptModal(false)} />
    </div>
  )
}
