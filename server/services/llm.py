from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

import httpx
import logging

from ..config import Settings


SYSTEM_PROMPT = (
    "You are an intelligent friend. Respond concisely and naturally, with clear reasoning. "
    "When using external document snippets, integrate them smoothly and cite as [Source: filename.pdf, page X]. "
    "If you don't know, say so. Avoid robotic tone."
)

logger = logging.getLogger(__name__)

async def stream_chat(user_text: str, settings: Settings) -> AsyncGenerator[str, None]:
    """
    Proxy streamed chat completion from OpenRouter and yield text tokens.
    """
    if not settings.OPENROUTER_API_KEY:
        logger.warning("stream_chat: OPENROUTER_API_KEY missing; falling back to echo tokenization")
        # No key present; fallback to echoing back the text token-by-token
        for ch in user_text:
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

    payload = {
        "model": settings.LLM_MODEL,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
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
