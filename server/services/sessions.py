from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import orjson


class SessionsManager:
    """Persist chat sessions and messages to JSON files under data/sessions."""

    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        data_dir = base_dir / "data"
        self._sessions_dir = data_dir / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def list_sessions(self) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []
        async with self._lock:
            for path in self._sessions_dir.glob("*.json"):
                data = await self._read_file(path)
                if not data:
                    continue
                session = data.get("session") or {}
                sessions.append(session)
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return sessions

    async def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        async with self._lock:
            session_id = str(uuid.uuid4())
            now = self._timestamp()
            session_title = (title or "New chat").strip() or "New chat"
            data = {
                "session": {
                    "session_id": session_id,
                    "title": session_title,
                    "created_at": now,
                    "updated_at": now,
                    "last_message_preview": "",
                },
                "messages": [
                    {
                        "id": str(uuid.uuid4()),
                        "role": "system",
                        "text": "Welcome! Use mic or type to chat. Upload documents to enable RAG.",
                        "created_at": now,
                    }
                ],
            }
            await self._write_session(session_id, data)
            return data

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read_session(session_id)
            if not data:
                raise ValueError("Session not found")
            return data

    async def append_message(self, session_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read_session(session_id)
            if not data:
                raise ValueError("Session not found")

            prepared = self._prepare_message(message)
            data["messages"].append(prepared)
            self._maybe_autoname(data, prepared)
            self._update_summary(data)
            await self._write_session(session_id, data)
            return {"session": data["session"], "message": prepared}

    async def update_title(self, session_id: str, title: str) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read_session(session_id)
            if not data:
                raise ValueError("Session not found")
            data["session"]["title"] = title.strip() or data["session"].get("title", "New chat")
            self._update_summary(data, touch=False)
            await self._write_session(session_id, data)
            return data["session"]

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            path = self._session_path(session_id)
            if path.exists():
                path.unlink()

    async def ensure_session(self, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read_session(session_id)
            if not data:
                raise ValueError("Session not found")
            return data["session"]

    async def _read_session(self, session_id: str) -> Dict[str, Any] | None:
        path = self._session_path(session_id)
        return await self._read_file(path)

    async def _read_file(self, path: Path) -> Dict[str, Any] | None:
        if not path.exists():
            return None
        async with aiofiles.open(path, "rb") as f:
            raw = await f.read()
        if not raw:
            return None
        return orjson.loads(raw)

    async def _write_session(self, session_id: str, data: Dict[str, Any]) -> None:
        path = self._session_path(session_id)
        async with aiofiles.open(path, "wb") as f:
            await f.write(orjson.dumps(data))

    def _session_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.json"

    def _prepare_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        prepared = dict(message)
        prepared.setdefault("id", str(uuid.uuid4()))
        prepared.setdefault("created_at", self._timestamp())
        prepared.setdefault("role", "assistant")
        prepared.setdefault("text", "")
        return prepared

    def _maybe_autoname(self, data: Dict[str, Any], message: Dict[str, Any]) -> None:
        session = data["session"]
        messages = data["messages"]
        if message.get("role") != "user":
            return
        if session.get("title") and session["title"] != "New chat":
            return
        # First non-system message becomes title
        user_text = (message.get("text") or "").strip()
        if not user_text:
            return
        preview = user_text.splitlines()[0][:60]
        session["title"] = preview or "New chat"

    def _update_summary(self, data: Dict[str, Any], *, touch: bool = True) -> None:
        session = data["session"]
        if touch:
            session["updated_at"] = self._timestamp()
        session["last_message_preview"] = self._build_preview(data["messages"])

    def _build_preview(self, messages: List[Dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "system":
                continue
            text = (message.get("text") or "").strip()
            if text:
                return text[:120]
        return ""

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


sessions_manager = SessionsManager()
