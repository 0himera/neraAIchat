from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import aiofiles
import faiss
import fitz  # type: ignore
import httpx
import numpy as np
import orjson
from fastapi import UploadFile

from ..config import Settings


@dataclass
class RAGChunk:
    chunk_id: str
    doc_id: str
    filename: str
    text: str
    chunk_index: int
    score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "filename": self.filename,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "score": self.score,
        }


class RAGEngine:
    META_VERSION = 1

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._initialized = False
        self._index: Optional[faiss.Index] = None
        self._dimension: Optional[int] = None
        self._chunks: List[Dict[str, Any]] = []  # all chunk metadata
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._active_chunk_indices: List[int] = []
        self._settings_cache: Optional[Settings] = None

        base_dir = Path(__file__).resolve().parents[1]
        data_dir = base_dir / "data"
        self._uploads_dir = data_dir / "uploads"
        self._index_dir = data_dir / "index"
        self._index_path = self._index_dir / "faiss.index"
        self._meta_path = self._index_dir / "metadata.json"

        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._index_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self, settings: Settings) -> None:
        async with self._lock:
            if self._initialized:
                return
            self._settings_cache = settings
            await self._load_state()
            self._initialized = True

    async def ensure_initialized(self, settings: Settings) -> None:
        if not self._initialized:
            await self.initialize(settings)

    async def ingest_upload(self, file: UploadFile, settings: Settings) -> Dict[str, Any]:
        await self.ensure_initialized(settings)

        try:
            content = await file.read()
        finally:
            close = getattr(file, "close", None)
            if callable(close):
                maybe_coro = close()
                if inspect.isawaitable(maybe_coro):
                    await maybe_coro

        if not content:
            raise ValueError("Empty file")

        original_name = file.filename or "document"
        extension = Path(original_name).suffix.lower()
        supported_extensions = {".pdf", ".txt", ".md", ".markdown", ".json"}
        if extension not in supported_extensions:
            raise ValueError("Unsupported file type. Allowed: PDF, TXT, MD, JSON")

        max_bytes = settings.MAX_PDF_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError("Document exceeds size limit")

        doc_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        safe_extension = ".md" if extension == ".markdown" else extension
        stored_path = self._uploads_dir / f"{doc_id}{safe_extension}"
        async with aiofiles.open(stored_path, "wb") as out:
            await out.write(content)

        text = self._extract_text(content, extension)
        chunks = self._chunk_text(text)
        if not chunks:
            raise ValueError("No text content extracted from document")

        embeddings = await self._embed_texts(chunks, settings)
        added = await self._add_chunks(
            doc_id=doc_id,
            filename=original_name,
            chunks=chunks,
            embeddings=embeddings,
            uploaded_at=timestamp,
        )

        return {
            "doc_id": doc_id,
            "filename": original_name,
            "chunks": added,
            "uploaded_at": timestamp,
        }

    async def list_documents(self) -> List[Dict[str, Any]]:
        docs = []
        for doc in self._docs.values():
            item = dict(doc)
            item.setdefault("enabled", True)
            docs.append(item)
        return docs

    async def set_document_enabled(self, doc_id: str, enabled: bool) -> Dict[str, Any]:
        async with self._lock:
            doc = self._docs.get(doc_id)
            if not doc:
                raise ValueError("Document not found")
            doc["enabled"] = bool(enabled)
            await self._refresh_active_chunks()
            await self._persist_state()
            return dict(doc)

    async def delete_document(self, doc_id: str) -> None:
        async with self._lock:
            doc = self._docs.get(doc_id)
            if not doc:
                raise ValueError("Document not found")
            # Remove embeddings/chunks for doc
            removed_indices = [i for i, chunk in enumerate(self._chunks) if chunk.get("doc_id") == doc_id]
            if removed_indices:
                self._chunks = [c for c in self._chunks if c.get("doc_id") != doc_id]
                await self._refresh_active_chunks()
            self._docs.pop(doc_id, None)
            await self._persist_state()
            # Remove stored file
            stored_path = next(self._uploads_dir.glob(f"{doc_id}.*"), None)
            if stored_path and stored_path.exists():
                stored_path.unlink()

    async def query(self, query: str, settings: Settings, top_k: int = 5) -> List[RAGChunk]:
        await self.ensure_initialized(settings)
        if not self._index or self._index.ntotal == 0 or not self._active_chunk_indices:
            return []

        query_embedding = await self._embed_texts([query], settings)
        if not query_embedding or not query_embedding[0]:
            return []

        vector = np.asarray(query_embedding, dtype="float32")
        faiss.normalize_L2(vector)
        scores, indices = self._index.search(vector, top_k)

        results: List[RAGChunk] = []
        for score, chunk_idx in zip(scores[0], indices[0]):
            if chunk_idx < 0 or chunk_idx >= len(self._active_chunk_indices):
                continue
            chunk_meta = self._chunks[self._active_chunk_indices[chunk_idx]]
            results.append(
                RAGChunk(
                    chunk_id=chunk_meta["chunk_id"],
                    doc_id=chunk_meta["doc_id"],
                    filename=chunk_meta["filename"],
                    text=chunk_meta["text"],
                    chunk_index=chunk_meta["chunk_index"],
                    score=float(score),
                )
            )
        return results

    async def _add_chunks(
        self,
        *,
        doc_id: str,
        filename: str,
        chunks: Iterable[str],
        embeddings: Iterable[Iterable[float]],
        uploaded_at: str,
    ) -> int:
        if self._settings_cache and len(self._docs) >= self._settings_cache.MAX_DOCS:
            raise ValueError("Document limit reached")

        chunk_texts = list(chunks)
        embeddings_list = [list(vec) for vec in embeddings]
        if not embeddings_list:
            raise ValueError("Received empty embeddings")

        embeddings_array = np.asarray(embeddings_list, dtype="float32")
        if embeddings_array.ndim != 2:
            raise ValueError("Embedding tensor must be 2-dimensional")
        if len(chunk_texts) != embeddings_array.shape[0]:
            raise ValueError("Chunk and embedding counts mismatch")
        faiss.normalize_L2(embeddings_array)
        normalized_embeddings = embeddings_array.tolist()

        dimension = embeddings_array.shape[1]

        async with self._lock:
            if self._dimension is None:
                self._dimension = dimension
            elif self._dimension != dimension:
                raise ValueError("Embedding dimensionality mismatch with existing index")

            for offset, text in enumerate(chunk_texts):
                self._chunks.append(
                    {
                        "chunk_id": str(uuid.uuid4()),
                        "doc_id": doc_id,
                        "filename": filename,
                        "text": text,
                        "chunk_index": offset,
                        "embedding": normalized_embeddings[offset],
                    }
                )

            chunk_count = len(normalized_embeddings)

            self._docs[doc_id] = {
                "doc_id": doc_id,
                "filename": filename,
                "chunks": chunk_count,
                "uploaded_at": uploaded_at,
                "enabled": True,
            }

            await self._refresh_active_chunks()
            await self._persist_state()

    def _ensure_index(self, dimension: int) -> None:
        if self._index is None:
            self._index = faiss.IndexFlatIP(dimension)
            self._dimension = dimension
        elif self._dimension != dimension:
            raise ValueError("Embedding dimensionality mismatch with existing index")

    async def _load_state(self) -> None:
        if self._meta_path.exists():
            async with aiofiles.open(self._meta_path, "rb") as meta_file:
                raw = await meta_file.read()
                if raw:
                    data = orjson.loads(raw)
                    if data.get("meta_version") == self.META_VERSION:
                        self._chunks = data.get("chunks", [])
                        self._docs = data.get("docs", {})
                        self._dimension = data.get("dimension")
        if self._index_path.exists() and self._dimension:
            self._index = faiss.read_index(str(self._index_path))
        await self._refresh_active_chunks(initial_load=True)

    async def _persist_state(self) -> None:
        payload = {
            "meta_version": self.META_VERSION,
            "dimension": self._dimension,
            "chunks": self._chunks,
            "docs": self._docs,
        }
        async with aiofiles.open(self._meta_path, "wb") as meta_file:
            await meta_file.write(orjson.dumps(payload))
        if self._index is not None:
            faiss.write_index(self._index, str(self._index_path))

    async def _refresh_active_chunks(self, *, initial_load: bool = False) -> None:
        enabled_doc_ids = {doc_id for doc_id, meta in self._docs.items() if meta.get("enabled", True)}
        self._active_chunk_indices = [i for i, meta in enumerate(self._chunks) if meta.get("doc_id") in enabled_doc_ids]
        if self._dimension is None:
            return
        if self._index is None:
            self._ensure_index(self._dimension)
        if self._index is None:
            return
        if self._index is None:
            return
        self._index.reset()
        if not self._active_chunk_indices:
            return
        await self._rebuild_index()

    async def _rebuild_index(self) -> None:
        if self._dimension is None or not self._active_chunk_indices:
            self._index = faiss.IndexFlatIP(self._dimension or 0) if self._dimension else None
            return
        if self._index is None:
            self._ensure_index(self._dimension)
        if self._index is None:
            return
        embeddings: List[List[float]] = []
        for idx in self._active_chunk_indices:
            emb = self._chunks[idx].get("embedding")
            if not emb:
                continue
            embeddings.append(emb)
        if not embeddings:
            return
        embeddings_array = np.asarray(embeddings, dtype="float32")
        faiss.normalize_L2(embeddings_array)
        self._index.add(embeddings_array)


    def _extract_text(self, content: bytes, extension: str) -> str:
        if extension == ".pdf":
            return self._extract_pdf(content)
        if extension == ".json":
            try:
                obj = json.loads(content.decode("utf-8"))
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON document")
            return json.dumps(obj, ensure_ascii=False, indent=2)
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1")

    def _extract_pdf(self, content: bytes) -> str:
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            texts = []
            for page in doc:
                texts.append(page.get_text("text"))
            return "\n".join(texts)
        finally:
            doc.close()

    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
        cleaned = text.strip()
        if not cleaned:
            return []

        words = cleaned.split()
        chunks: List[str] = []
        start = 0
        while start < len(words):
            end = min(len(words), start + chunk_size)
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            if end == len(words):
                break
            start = max(end - overlap, start + 1)
        return chunks

    async def _embed_texts(self, texts: Iterable[str], settings: Settings) -> List[List[float]]:
        raw_texts = list(texts)
        if not raw_texts:
            return []

        stripped_texts = [t.strip() for t in raw_texts]
        for chunk in stripped_texts:
            if not chunk:
                raise ValueError("Encountered empty chunk during embedding request")

        if not settings.JINA_API_KEY:
            raise ValueError("JINA_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
            "Content-Type": "application/json",
        }
        url = "https://api.jina.ai/v1/embeddings"
        batch_default = getattr(settings, "JINA_EMBED_BATCH", 16) or 16

        ordered_embeddings: List[Optional[List[float]]] = [None] * len(stripped_texts)

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=60.0)) as client:
            i = 0
            while i < len(stripped_texts):
                batch_size = min(batch_default, len(stripped_texts) - i)
                while batch_size > 0:
                    batch_texts = stripped_texts[i : i + batch_size]
                    payload = {
                        "model": settings.JINA_EMBEDDINGS_MODEL,
                        "input": batch_texts,
                    }
                    try:
                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                        data = response.json()
                        received = data.get("data", [])
                        if len(received) != batch_size:
                            raise ValueError("Embedding service returned mismatched number of vectors")
                        for offset, item in enumerate(received):
                            embedding = item.get("embedding")
                            if not embedding:
                                raise ValueError("Embedding service returned empty embedding")
                            ordered_embeddings[i + offset] = embedding
                        break
                    except httpx.HTTPStatusError as exc:
                        if exc.response is not None and exc.response.status_code == 413 and batch_size > 1:
                            batch_size = max(1, batch_size // 2)
                            continue
                        raise
                i += batch_size

        if any(emb is None for emb in ordered_embeddings):
            raise ValueError("Failed to generate embeddings for all chunks")

        return [emb for emb in ordered_embeddings if emb is not None]


rag_engine = RAGEngine()
