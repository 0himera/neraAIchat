from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Iterable, Sequence

import httpx
import logging

from ..config import Settings
from .rag import RAGChunk


SYSTEM_PROMPT = (
    "You are an intelligent friend. Respond concisely and naturally, with clear reasoning. "
    "When using external document snippets, integrate them smoothly. "
    "If you don't know, say so. Avoid robotic tone."
)

logger = logging.getLogger(__name__)

MAX_CONTEXT_SNIPPET_CHARS = 1200


def _format_rag_context(chunks: Sequence[RAGChunk]) -> str:
    snippets = []
    for idx, chunk in enumerate(chunks, start=1):
        text = (chunk.text or "").strip()
        if not text:
            continue
        if len(text) > MAX_CONTEXT_SNIPPET_CHARS:
            text = text[:MAX_CONTEXT_SNIPPET_CHARS].rstrip() + "…"
        snippets.append(
            f"[{idx}] Source: {chunk.filename} (chunk {chunk.chunk_index})\n{text}"
        )
    return "\n\n".join(snippets)


async def stream_chat(
    user_text: str,
    settings: Settings,
    *,
    context_chunks: Sequence[RAGChunk] | None = None,
    system_prompt: str | None = None,
    memory_notes: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Proxy streamed chat completion from OpenRouter and yield text tokens.
    """
    if not settings.OPENROUTER_API_KEY:
        logger.warning("stream_chat: OPENROUTER_API_KEY missing; falling back to echo tokenization")
        # No key present; fallback to echoing back the text token-by-token
        context_header = ""
        if context_chunks:
            context_header = _format_rag_context(context_chunks)
        fallback_text = user_text
        if context_header:
            fallback_text = context_header + "\n\nUser Question:\n" + user_text
        for ch in fallback_text:
            yield ch
            await asyncio.sleep(0.005)
        return

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        # Recommended by OpenRouter for routing/analytics
        "HTTP-Referer": settings.FRONTEND_ORIGIN or "http://localhost:5173",
        "X-Title": "NeraAIchat",
    }

    base_prompt = (system_prompt or SYSTEM_PROMPT).strip() or SYSTEM_PROMPT
    messages: list[dict[str, str]] = [
        {"role": "system", "content": base_prompt},
    ]
    if memory_notes:
        memory_blob = memory_notes.strip()
        if memory_blob:
            messages.append({"role": "system", "content": f"Conversation memory guidelines:\n{memory_blob}"})
    if context_chunks:
        context_blob = _format_rag_context(context_chunks)
        if context_blob:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Relevant document snippets (use for grounding, cite as [Source: filename, chunk index]):\n"
                        + context_blob
                    ),
                }
            )
    messages.append({"role": "user", "content": user_text})

    payload = {
        "model": settings.LLM_MODEL,
        "stream": True,
        "messages": messages,
    }

    timeout = httpx.Timeout(30.0, read=60.0)
    logger.info("stream_chat: POST %s model=%s", settings.OPENROUTER_API_URL, settings.LLM_MODEL)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            stream_ctx = client.stream("POST", settings.OPENROUTER_API_URL, headers=headers, json=payload)
            async with stream_ctx as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        # SSE comment/heartbeat
                        continue
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        # OpenAI-compatible delta format
                        try:
                            delta = obj["choices"][0]["delta"]
                            content = delta.get("content")
                            if content:
                                yield content
                        except Exception:
                            # Non-standard chunk; try fallback path
                            try:
                                content = obj["choices"][0]["message"]["content"]
                                if content:
                                    yield content
                            except Exception:
                                continue
        except httpx.HTTPStatusError as e:
            # Log status and body to help diagnose model slug or key issues
            body = None
            try:
                body = e.response.text
            except Exception:
                pass
            logger.error("OpenRouter HTTP error: status=%s body=%s", getattr(e.response, 'status_code', None), body)
            raise
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith(":"):
                    # SSE comment/heartbeat
                    continue
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    # OpenAI-compatible delta format
                    try:
                        delta = obj["choices"][0]["delta"]
                        content = delta.get("content")
                        if content:
                            yield content
                    except Exception:
                        # Non-standard chunk; try fallback path
                        try:
                            content = obj["choices"][0]["message"]["content"]
                            if content:
                                yield content
                        except Exception:
                            continue
