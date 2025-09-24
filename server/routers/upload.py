from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..config import Settings
from ..services.rag import rag_engine

router = APIRouter()


def get_settings() -> Settings:
    return Settings()


@router.post("/upload/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        result = await rag_engine.ingest_upload(file, settings)
        result["message"] = "PDF uploaded and indexed"
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
