import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useDispatch, useSelector } from 'react-redux'
import { setSystemPrompt, setMemoryNotes } from '../slices/settingsSlice.js'

export default function PromptSettingsModal({ open, onClose }) {
  const dispatch = useDispatch()
  const { systemPrompt, memoryNotes } = useSelector(s => s.settings)
  const [promptDraft, setPromptDraft] = useState(systemPrompt)
  const [memoryDraft, setMemoryDraft] = useState(memoryNotes)

  useEffect(() => {
    if (!open) return
    setPromptDraft(systemPrompt)
    setMemoryDraft(memoryNotes)
  }, [open, systemPrompt, memoryNotes])

  if (!open) return null

  const container = document.body

  const handleSave = () => {
    dispatch(setSystemPrompt(promptDraft))
    dispatch(setMemoryNotes(memoryDraft))
    onClose?.()
  }

  return createPortal(
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-panel">
        <div className="modal-header">
          <h2>System Settings</h2>
          <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-content">
          <label className="modal-label" htmlFor="systemPrompt">
            System Prompt
          </label>
          <textarea
            id="systemPrompt"
            className="glass-textarea"
            rows={6}
            value={promptDraft}
            onChange={e => setPromptDraft(e.target.value)}
            placeholder="Define assistant behavior, tone, or constraints"
          />

          <label className="modal-label" htmlFor="memoryNotes">
            Conversation Memory
          </label>
          <textarea
            id="memoryNotes"
            className="glass-textarea"
            rows={6}
            value={memoryDraft}
            onChange={e => setMemoryDraft(e.target.value)}
            placeholder="Short- and long-term memory notes"
          />
        </div>

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn primary" onClick={handleSave}>
            Save
          </button>
        </div>
      </div>
    </div>,
    container,
  )
}
