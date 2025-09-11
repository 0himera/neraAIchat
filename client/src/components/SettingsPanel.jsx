import React from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { setEnableRag, setTtsVoice, setChunkMs } from '../slices/settingsSlice.js'

export default function SettingsPanel() {
  const dispatch = useDispatch()
  const { enableRag, ttsVoice, chunkMs } = useSelector(s => s.settings)

  return (
    <div className="card">
      <div className="card-title">Settings</div>
      <div className="row">
        <label className="switch">
          <input type="checkbox" checked={enableRag} onChange={e => dispatch(setEnableRag(e.target.checked))} />
          <span>Enable RAG</span>
        </label>
      </div>
      <div className="row">
        <label>Voice:</label>
        <select value={ttsVoice} onChange={e => dispatch(setTtsVoice(e.target.value))}>
          <option value="en">English</option>
          <option value="ru">Russian</option>
        </select>
      </div>
      <div className="row">
        <label>Chunk (ms):</label>
        <input className="input small" type="number" min={100} max={1000} step={50} value={chunkMs} onChange={e => dispatch(setChunkMs(e.target.value))} />
      </div>
    </div>
  )
}
