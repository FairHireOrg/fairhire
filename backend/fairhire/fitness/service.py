"""Orchestration for the deterministic analyze pipeline."""

from __future__ import annotations

import os
import tempfile
from typing import Any

from fairhire.fitness.rubric import StyleMode, score_resume
from fairhire.parser import parse_pdf


def load_resume_text(resume_text: str | None = None, resume_path: str | None = None) -> str:
    if resume_text and resume_text.strip():
        return resume_text
    if not resume_path:
        raise ValueError("Provide resume_text or resume_path")
    lower = resume_path.lower()
    if lower.endswith(".pdf"):
        return parse_pdf(resume_path)
    if lower.endswith(".docx"):
        from fairhire.fitness.docx_io import read_docx_text

        with open(resume_path, "rb") as f:
            return read_docx_text(f.read())
    if lower.endswith((".txt", ".md")):
        with open(resume_path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        if not text:
            raise ValueError("Resume text file is empty")
        return text
    raise ValueError("Unsupported resume format. Use PDF, DOCX, or TXT.")


def analyze_fitness(
    job_description: str,
    resume_text: str | None = None,
    resume_path: str | None = None,
    style_mode: StyleMode = "balanced",
    config: Any | None = None,
    confirmations: dict[str, bool] | None = None,
    requirements: list[dict] | None = None,
) -> dict[str, Any]:
    if job_description is None:
        raise ValueError("job_description is required")

    text = load_resume_text(resume_text=resume_text, resume_path=resume_path)
    report = score_resume(
        text,
        job_description or "",
        style_mode=style_mode,
        config=config,
        preextracted=True,
        confirmations=confirmations,
        requirements=requirements,
    )
    payload = report.to_dict()
    payload["resume_text"] = text
    try:
        from fairhire.fitness.document import document_from_text

        payload["document"] = document_from_text(text).to_dict()
    except Exception:
        payload["document"] = None
    return payload


def score_document(document: dict[str, Any]) -> dict[str, Any]:
    """Re-score an edited ResumeDocument: render canonical text, re-parse, re-score."""
    from fairhire.fitness.ats import evaluate_ats
    from fairhire.fitness.document import ResumeDocument, document_from_text, document_to_text
    from fairhire.fitness.ner import parse_resume

    doc = ResumeDocument.from_dict(document)
    text = document_to_text(doc)
    result = evaluate_ats(parse_resume(text))
    return {
        "document": doc.to_dict(),
        "resume_text": text,
        "ats_score": round(result.score, 1),
        "ats_grade": result.grade,
        "dimensions": [d.to_dict() for d in result.dimensions],
        "recommendations": [r.to_dict() for r in result.recommendations],
        "issues_remaining": len(result.recommendations),
        "scorable": bool(text.strip()),
    }


def document_from_resume_text(resume_text: str) -> dict[str, Any]:
    """Parse free text into a ResumeDocument plus its ATS re-score."""
    from fairhire.fitness.document import document_from_text

    return score_document(document_from_text(resume_text).to_dict())


def analyze_upload_bytes(
    file_bytes: bytes,
    filename: str,
    job_description: str,
    style_mode: StyleMode = "balanced",
    config: Any | None = None,
    confirmations: dict[str, bool] | None = None,
    requirements: list[dict] | None = None,
) -> dict[str, Any]:
    suffix = os.path.splitext(filename or "resume.pdf")[1].lower() or ".pdf"
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise ValueError("Unsupported file type. Upload PDF, DOCX, or TXT.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return analyze_fitness(
            job_description=job_description,
            resume_path=tmp_path,
            style_mode=style_mode,
            config=config,
            confirmations=confirmations,
            requirements=requirements,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
