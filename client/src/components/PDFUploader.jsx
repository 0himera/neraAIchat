import React, { useState } from 'react'

const API_URL = 'http://localhost:8000/api/rag/documents'
const ACCEPTED_TYPES = '.pdf,.txt,.md,.markdown,.json'

export default function DocumentUploader() {
  const [status, setStatus] = useState('')

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
    } catch (err) {
      setStatus(`Error: ${err.message || err}`)
    } finally {
      e.target.value = ''
    }
  }

  return (
    <div className="card">
      <div className="card-title">Document Upload</div>
      <div className="card-subtitle">Supports PDF, TXT, Markdown, JSON</div>
      <input type="file" accept={ACCEPTED_TYPES} onChange={onChange} />
      <div className="status">{status}</div>
    </div>
  )
}
