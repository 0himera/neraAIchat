import React, { useState } from 'react'
import ManageFiles from './ManageFiles.jsx'

const API_URL = 'http://localhost:8000/api/rag/documents'
const ACCEPTED_TYPES = '.pdf,.txt,.md,.markdown,.json'

export default function DocumentUploader() {
  const [status, setStatus] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)
  const [showManager, setShowManager] = useState(false)

  const onChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    setStatus(`Uploading ${file.name}...`)
    try {
      const res = await fetch(API_URL, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || res.statusText)
      }
      const data = await res.json()
      setStatus(`Indexed ${data.filename} (chunks=${data.chunks})`)
      setRefreshToken(prev => prev + 1)
      setShowManager(true)
    } catch (err) {
      setStatus(`Error: ${err.message || err}`)
    } finally {
      e.target.value = ''
    }
  }

  return (
    <>
      <div className="card">
        <div className="card-title">Document Upload</div>
        <div className="card-subtitle">Supports PDF, TXT, Markdown, JSON</div>
        <label className="glass-input">
          <span>Browse</span>
          <input className="file-hidden" type="file" accept={ACCEPTED_TYPES} onChange={onChange} />
        </label>
        <div className="row">
          <div className="status grow">{status}</div>
          <button type="button" className="btn" onClick={() => setShowManager(v => !v)}>
            {showManager ? 'Hide Manage Files' : 'Manage Files'}
          </button>
        </div>
      </div>
      {showManager && <ManageFiles refreshToken={refreshToken} />}
    </>
  )
}
