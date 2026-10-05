"""FairHire Resume–JD fitness API (rule-based scoring, optional LLM matching)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from fairhire.config import Config
from fairhire.fitness.jev_parse import jev_parse_text
from fairhire.fitness.service import (
    analyze_fitness,
    analyze_upload_bytes,
    document_from_resume_text,
    load_resume_text,
    parse_instant_batch,
    parse_instant_text,
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


@app.get("/api/jev/health")
def jev_health() -> dict[str, Any]:
    """NanoJev inference service status for the schema-fill parser."""
    import json as _json
    import urllib.request

    from fairhire.fitness.jev_parse import NANOJEV_URL

    try:
        req = urllib.request.Request(f"{NANOJEV_URL}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        return {"available": bool(data.get("ready")), "url": NANOJEV_URL, "detail": data}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "url": NANOJEV_URL, "detail": {"error": str(exc)}}


class JevParseRequest(BaseModel):
    resume_text: str = Field(min_length=1, max_length=100000)


@app.post("/api/parse/jev")
def parse_jev(payload: JevParseRequest) -> dict[str, Any]:
    """Parse resume text into a JSON Resume schema document via NanoJev.

    Deterministic NER supplies exact fields and candidate pools; the NanoJev
    decision service ranks candidates and fills gaps. Falls back to the
    deterministic parse when the inference service is unreachable.
    """
    try:
        return jev_parse_text(payload.resume_text).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Jev parse failed")
        raise HTTPException(status_code=500, detail="Could not parse the resume text.") from exc


@app.post("/api/parse/jev/pdf")
async def parse_jev_pdf(resume: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a PDF, extract layout text, parse into JSON Resume via NanoJev."""
    data = await resume.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Resume uploads must be 10 MB or smaller.")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded resume is empty")
    suffix = os.path.splitext(resume.filename or "resume.pdf")[1].lower() or ".pdf"
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Upload PDF, DOCX, TXT, or Markdown.")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        text = load_resume_text(resume_path=tmp_path)
        return jev_parse_text(text).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Jev PDF parse failed")
        raise HTTPException(status_code=500, detail="Could not parse the uploaded file.") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


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


class InstantParseRequest(BaseModel):
    resume_text: str = Field(min_length=1, max_length=100000)


class InstantBatchRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=25)


@app.post("/api/parse/instant")
async def parse_instant(payload: InstantParseRequest) -> dict[str, Any]:
    """NanoJev-style instant parse from raw text: one pass, distributions out."""
    if not payload.resume_text.strip():
        raise HTTPException(status_code=400, detail="Provide resume_text to parse.")
    try:
        return await run_in_threadpool(parse_instant_text, payload.resume_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Instant parse failed")
        raise HTTPException(status_code=500, detail="Could not parse the resume text.") from exc


@app.post("/api/parse/instant/batch")
async def parse_instant_batch_route(payload: InstantBatchRequest) -> dict[str, Any]:
    """Batch independent resume texts — one backbone pass each, no cross-talk."""
    try:
        results = await run_in_threadpool(parse_instant_batch, payload.texts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logging.exception("Instant batch parse failed")
        raise HTTPException(status_code=500, detail="Could not parse the batch.") from exc
    return {"engine": "nanojev-instant", "count": len(results), "results": results}


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


@app.post("/api/jev/export")
def export_jev(payload: DocumentUpdate) -> Response:
    """Render a JSON Resume schema document as an ATS-safe .docx download."""
    from fairhire.fitness.docx_io import export_jsonresume_docx

    doc = payload.document
    if not isinstance(doc, dict) or not doc.get("basics"):
        raise HTTPException(status_code=400, detail="Provide a JSON Resume document with a basics section.")
    try:
        blob = export_jsonresume_docx(doc)
    except Exception as exc:  # noqa: BLE001
        logging.exception("JSON Resume export failed")
        raise HTTPException(status_code=500, detail="Could not export the document.") from exc
    name = str((doc.get("basics") or {}).get("name") or "resume").strip().lower().replace(" ", "-") or "resume"
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
