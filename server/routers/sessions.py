from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, status

from ..services.sessions import sessions_manager

router = APIRouter()


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    return await sessions_manager.list_sessions()


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(payload: Dict[str, Any] | None = Body(default=None)) -> Dict[str, Any]:
    title = (payload or {}).get("title") if payload else None
    return await sessions_manager.create_session(title=title)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    try:
        return await sessions_manager.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def append_message(session_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    role = (payload.get("role") or "").strip() if isinstance(payload, dict) else ""
    text = payload.get("text") if isinstance(payload, dict) else None
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text is required")
    role = role or "assistant"
    if role not in {"user", "assistant", "system"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    try:
        return await sessions_manager.append_message(session_id, {"role": role, "text": text})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    title = (payload.get("title") or "").strip() if isinstance(payload, dict) else ""
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is required")
    try:
        return await sessions_manager.update_title(session_id, title)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    await sessions_manager.delete_session(session_id)
    return {"status": "deleted"}
