"""FairHire Resume–JD fitness API (rule-based scoring, optional LLM matching)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from fairhire.config import Config
from fairhire.fitness.service import (
    analyze_fitness,
    analyze_upload_bytes,
    document_from_resume_text,
    score_document,
)
from fairhire.fitness.ner import parse_job_description
from fairhire.fitness.requirements import extract_checklist, validate_checklist, requirement_id
from fairhire.fitness.llm_extract import extract_requirements

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
        "http://localhost:3002",
        "http://127.0.0.1:3002",
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
        "extraction": "deterministic",
        "ai_available": cfg.llm_extraction_enabled,
        "deepseek_model": cfg.deepseek_model if cfg.llm_extraction_enabled else None,
    }


class ResumePayload(BaseModel):
    document: dict[str, Any]


class ExportPayload(ResumePayload):
    format: str = Field("docx", pattern="^(docx|txt)$")


@app.post("/api/resume/import")
async def resume_import(
    resume: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
) -> dict[str, Any]:
    """Upload (PDF/DOCX/TXT/MD) or paste text -> canonical document + ATS readout."""
    from fairhire.resume.service import import_resume

    try:
        data = None
        name = ""
        if resume is not None and resume.filename:
            data = await resume.read(10 * 1024 * 1024 + 1)
            name = resume.filename
        if resume_text is not None and len(resume_text) > 100000:
            raise ValueError("Pasted resumes must be under 100,000 characters.")
        return await run_in_threadpool(import_resume, data, name, resume_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Resume import failed")
        raise HTTPException(status_code=500, detail="Could not read this resume. Try pasting the text instead.") from exc


@app.post("/api/resume/score")
async def resume_score(payload: ResumePayload) -> dict[str, Any]:
    """Re-score an edited document. Pure and deterministic: same document, same result."""
    from fairhire.resume.model import Resume
    from fairhire.resume.service import score_resume

    try:
        return await run_in_threadpool(score_resume, Resume.from_dict(payload.document))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/resume/export")
async def resume_export(payload: ExportPayload) -> Response:
    from fairhire.resume.export import export_docx, export_txt
    from fairhire.resume.model import Resume

    try:
        resume = Resume.from_dict(payload.document)
        if payload.format == "txt":
            blob, media, ext = export_txt(resume), "text/plain; charset=utf-8", "txt"
        else:
            blob = await run_in_threadpool(export_docx, resume)
            media, ext = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    name = "-".join((resume.contact.name or "resume").lower().split()) or "resume"
    return Response(content=blob, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})


@app.post("/api/analyze")
async def analyze(
    job_description: str = Form(""),
    resume: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
    requirements: str | None = Form(None),
) -> dict[str, Any]:
    checklist = None
    if len(job_description) > 30000 or (resume_text and len(resume_text) > 100000):
        raise HTTPException(status_code=400, detail="Use a job description under 30,000 characters and resume under 100,000 characters.")
    if requirements is not None:
        try:
            checklist = json.loads(requirements)
            validate_checklist(checklist, parse_job_description(job_description))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid checklist: " + str(exc)) from exc
    try:
        if resume is not None and resume.filename:
            if resume_text and resume_text.strip():
                raise ValueError("Choose either upload or pasted resume text.")
            data = await resume.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("Resume uploads must be 10 MB or smaller.")
            if not data:
                raise ValueError("Uploaded resume is empty")
            return await run_in_threadpool(analyze_upload_bytes,
                file_bytes=data,
                filename=resume.filename,
                job_description=job_description,
                requirements=checklist,
            )
        if resume_text and resume_text.strip():
            return await run_in_threadpool(analyze_fitness,
                job_description=job_description,
                resume_text=resume_text,
                requirements=checklist,
            )
        raise ValueError("Provide a resume file or resume_text")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Analysis failed")
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again or paste the resume as text.") from exc


class SuggestRequest(BaseModel):
    job_description: str = Field(min_length=1, max_length=30000)


class DocumentUpdate(BaseModel):
    document: dict[str, Any]


@app.get("/api/document")
async def get_document(resume_text: str = Query("", max_length=100000)) -> dict[str, Any]:
    """Parse free text into a ResumeDocument plus its ATS re-score."""
    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Provide resume_text to build a document.")
    try:
        return await run_in_threadpool(document_from_resume_text, resume_text)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Document parse failed")
        raise HTTPException(status_code=500, detail="Could not build a document from the text.") from exc


@app.put("/api/document")
async def put_document(payload: DocumentUpdate) -> dict[str, Any]:
    """Accept an edited ResumeDocument, re-score its canonical text, return issues."""
    try:
        return await run_in_threadpool(score_document, payload.document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Document scoring failed")
        raise HTTPException(status_code=500, detail="Could not score the document.") from exc


@app.post("/api/document/export")
async def export_document(payload: DocumentUpdate) -> Response:
    """Render an edited ResumeDocument as an ATS-safe .docx download."""
    from fairhire.fitness.document import ResumeDocument
    from fairhire.fitness.docx_io import export_document_docx

    try:
        doc = ResumeDocument.from_dict(payload.document)
        blob = await run_in_threadpool(export_document_docx, doc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Document export failed")
        raise HTTPException(status_code=500, detail="Could not export the document.") from exc
    name = (doc.contact.name or "resume").strip().lower().replace(" ", "-") or "resume"
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{name}-ats.docx"'},
    )


@app.post("/api/requirements/suggest")
def suggest(payload: SuggestRequest) -> dict[str, Any]:
    cfg = Config()
    if not cfg.llm_extraction_enabled:
        return {"status": "deterministic_only", "suggestions": []}
    extracted = extract_requirements(payload.job_description, cfg)
    if extracted is None:
        return {"status": "deterministic_fallback", "suggestions": []}
    jd = parse_job_description(payload.job_description)
    baseline = {r.text.casefold() for r in extract_checklist(jd)}
    suggestions = []
    seen = set()
    for row in extracted:
        try:
            valid = validate_checklist([row.to_dict()], jd)[0]
        except (ValueError, IndexError):
            continue
        key = requirement_id(valid)
        if valid.text.casefold() not in baseline and key not in seen:
            seen.add(key)
            suggestions.append(dict(valid.to_dict(), id=key))
    return {"status": "llm_extracted", "suggestions": suggestions}
