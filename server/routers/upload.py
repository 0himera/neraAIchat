from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi import Depends
from fastapi import status

from ..config import Settings

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"


def get_settings() -> Settings:
    return Settings()


@router.post("/upload/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")

    MAX_BYTES = settings.MAX_PDF_MB * 1024 * 1024
    doc_id = str(uuid.uuid4())
    target_path = UPLOADS_DIR / f"{doc_id}.pdf"

    size = 0
    try:
        async with aiofiles.open(target_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF exceeds size limit")
                await out.write(chunk)
    finally:
        await file.close()

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "size": size,
        "message": "Uploaded. Indexing will be performed separately.",
    }
