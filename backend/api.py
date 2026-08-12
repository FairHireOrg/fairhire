"""FairHire Resume–JD fitness API (deterministic, LLM-free)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from fairhire.config import Config
from fairhire.fitness.service import analyze_fitness, analyze_upload_bytes

app = FastAPI(
    title="FairHire Fitness API",
    description="Deterministic Resume–JD fitness scoring with NER-style term matching.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    cfg = Config()
    return {
        "status": "ok",
        "product": "resume_jd_fitness",
        "mode": "deterministic_ner",
        "extraction": "hybrid" if cfg.llm_extraction_enabled else "deterministic",
        "deepseek_model": cfg.deepseek_model if cfg.llm_extraction_enabled else None,
    }


@app.post("/api/analyze")
async def analyze(
    job_description: str = Form(...),
    resume: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
) -> dict[str, Any]:
    try:
        if resume is not None and resume.filename:
            data = await resume.read()
            if not data:
                raise ValueError("Uploaded resume is empty")
            return analyze_upload_bytes(
                file_bytes=data,
                filename=resume.filename,
                job_description=job_description,
            )
        if resume_text and resume_text.strip():
            return analyze_fitness(
                job_description=job_description,
                resume_text=resume_text,
            )
        raise ValueError("Provide a resume file or resume_text")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
