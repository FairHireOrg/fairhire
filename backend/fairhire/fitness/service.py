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
    if lower.endswith((".txt", ".md")):
        with open(resume_path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        if not text:
            raise ValueError("Resume text file is empty")
        return text
    raise ValueError("Unsupported resume format. Use PDF or TXT.")


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
    return payload


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
    if suffix not in {".pdf", ".txt", ".md"}:
        raise ValueError("Unsupported file type. Upload PDF or TXT.")

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
