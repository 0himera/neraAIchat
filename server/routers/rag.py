from __future__ import annotations

from typing import List

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status

from ..config import Settings
from ..services.rag import RAGChunk, rag_engine

router = APIRouter()


def get_settings() -> Settings:
    return Settings()


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def ingest_document(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    try:
        result = await rag_engine.ingest_upload(file, settings)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Embedding service error: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/documents", response_model=List[dict])
async def list_documents(settings: Settings = Depends(get_settings)):
    await rag_engine.ensure_initialized(settings)
    return await rag_engine.list_documents()


@router.get("/documents/search", response_model=List[dict])
async def search_documents(
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    settings: Settings = Depends(get_settings),
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    await rag_engine.ensure_initialized(settings)
    chunks = await rag_engine.query(query, settings, top_k=top_k)
    return [chunk.to_dict() for chunk in chunks]


@router.patch("/documents/{doc_id}", response_model=dict)
async def update_document(
    doc_id: str = Path(..., description="Document identifier"),
    enabled: bool = Query(..., description="Enable (true) or disable (false) document for retrieval"),
    settings: Settings = Depends(get_settings),
):
    await rag_engine.ensure_initialized(settings)
    try:
        return await rag_engine.set_document_enabled(doc_id, enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str = Path(..., description="Document identifier"),
    settings: Settings = Depends(get_settings),
):
    await rag_engine.ensure_initialized(settings)
    try:
        await rag_engine.delete_document(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
