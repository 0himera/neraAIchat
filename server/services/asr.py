from __future__ import annotations

import asyncio
import io
import subprocess
import wave
from functools import lru_cache
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from ..config import Settings


def decode_opus_to_wav_bytes(opus_bytes: bytes, ffmpeg_path: Optional[str]) -> bytes:
    """Use ffmpeg to decode Ogg/Opus bytes to mono 16kHz WAV bytes."""
    if not ffmpeg_path:
        raise RuntimeError("FFMPEG_PATH is not configured; cannot decode Opus audio")
    # ffmpeg -i pipe:0 -ar 16000 -ac 1 -f wav pipe:1
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "wav",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate(opus_bytes)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {err.decode('utf-8', 'ignore')}")
    return out


def wav_bytes_to_f32_mono(wav_bytes: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        nch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        fr = wf.getframerate()
        nframes = wf.getnframes()
        pcm = wf.readframes(nframes)
    if sampwidth != 2:
        raise ValueError("expected 16-bit PCM")
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if nch > 1:
        audio = audio.reshape(-1, nch).mean(axis=1)
    # If not 16k, we already forced 16k via ffmpeg
    return audio


@lru_cache(maxsize=1)
def _load_model(model_size: str) -> WhisperModel:
    # Try CUDA first, then CPU fallback
    try:
        return WhisperModel(model_size, device="cuda", compute_type="float16")
    except Exception:
        return WhisperModel(model_size, device="cpu", compute_type="int8")


async def transcribe_opus(opus_bytes: bytes, settings: Settings) -> str:
    """Decode Opus and run faster-whisper transcription. Returns final text."""
    # Decode to WAV using ffmpeg (blocking, so run in thread)
    wav_bytes = await asyncio.to_thread(decode_opus_to_wav_bytes, opus_bytes, settings.__dict__.get("FFMPEG_PATH"))
    audio = wav_bytes_to_f32_mono(wav_bytes)

    model = await asyncio.to_thread(_load_model, settings.ASR_MODEL)

    # Run transcription in a worker thread
    def _do_transcribe() -> str:
        segments, info = model.transcribe(
            audio,
            language=None,  # auto-detect
            beam_size=1,
            vad_filter=True,
        )
        text_parts = []
        for seg in segments:
            text_parts.append(seg.text)
        return " ".join(t.strip() for t in text_parts if t.strip())

    text = await asyncio.to_thread(_do_transcribe)
    return text or ""
