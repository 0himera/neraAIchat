import React, { useState } from 'react'

export default function PDFUploader() {
  const [status, setStatus] = useState('')

  const onChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    setStatus('Uploading...')
    try {
      const res = await fetch('http://localhost:8000/api/upload/pdf', { method: 'POST', body: fd })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setStatus(`Uploaded: ${data.filename} (doc_id=${data.doc_id})`)
    } catch (err) {
      setStatus(`Error: ${err}`)
    }
  }

  return (
    <div className="card">
      <div className="card-title">PDF Upload</div>
      <input type="file" accept="application/pdf" onChange={onChange} />
      <div className="status">{status}</div>
    </div>
  )
}
