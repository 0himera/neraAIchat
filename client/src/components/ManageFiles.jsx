import React, { useCallback, useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000/api/rag/documents'

export default function ManageFiles({ refreshToken = 0 }) {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(API_BASE)
      if (!res.ok) {
        throw new Error((await res.text()) || res.statusText)
      }
      const data = await res.json()
      setDocs(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message || 'Failed to load documents')
    } finally {
      setLoading(false)
      setBusyId(null)
    }
  }, [])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments, refreshToken])

  const toggleDocument = async (doc) => {
    if (!doc) return
    setBusyId(doc.doc_id)
    try {
      const url = `${API_BASE}/${encodeURIComponent(doc.doc_id)}?enabled=${doc.enabled ? 'false' : 'true'}`
      const res = await fetch(url, { method: 'PATCH' })
      if (!res.ok) {
        throw new Error((await res.text()) || res.statusText)
      }
      await loadDocuments()
    } catch (err) {
      setError(err.message || 'Failed to update document')
    } finally {
      setBusyId(null)
    }
  }

  const deleteDocument = async (doc) => {
    if (!doc) return
    const confirmDelete = window.confirm(`Delete ${doc.filename}? This cannot be undone.`)
    if (!confirmDelete) return
    setBusyId(doc.doc_id)
    try {
      const url = `${API_BASE}/${encodeURIComponent(doc.doc_id)}`
      const res = await fetch(url, { method: 'DELETE' })
      if (!res.ok) {
        throw new Error((await res.text()) || res.statusText)
      }
      await loadDocuments()
    } catch (err) {
      setError(err.message || 'Failed to delete document')
    } finally {
      setBusyId(null)
    }
  }

  const formatDate = (iso) => {
    if (!iso) return 'Unknown'
    try {
      return new Date(iso).toLocaleString()
    } catch {
      return iso
    }
  }

  return (
    <div className="card">
      <div className="card-title">Manage Files</div>
      {error && <div className="status error">{error}</div>}
      {loading && <div className="status">Loading…</div>}
      {!loading && docs.length === 0 && <div className="status">No documents indexed yet.</div>}
      <div className="file-list">
        {docs.map(doc => (
          <div key={doc.doc_id} className={`file-row ${doc.enabled ? '' : 'disabled'}`}>
            <div className="file-meta">
              <div className="file-name">{doc.filename}</div>
              <div className="file-info">
                Chunks: {doc.chunks ?? 0} · Uploaded: {formatDate(doc.uploaded_at)} · Status: {doc.enabled ? 'Enabled' : 'Disabled'}
              </div>
            </div>
            <div className="file-actions">
              <button
                type="button"
                className="btn small"
                onClick={() => toggleDocument(doc)}
                disabled={busyId === doc.doc_id}
              >
                {doc.enabled ? 'Disable' : 'Enable'}
              </button>
              <button
                type="button"
                className="btn danger small"
                onClick={() => deleteDocument(doc)}
                disabled={busyId === doc.doc_id}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
