"""Import / score / export orchestration for the resume editor."""

from __future__ import annotations

from typing import Any

from fairhire.fitness.ats import evaluate_ats
from fairhire.fitness.ner import parse_resume as ats_parse
from fairhire.resume.extract import extract_text
from fairhire.resume.model import Resume
from fairhire.resume.parse import parse_resume_text
from fairhire.resume.render import render_with_map

RULESET = "ats-rules-1"

# Recommendations with no line reference still belong to a place in the document.
_CODE_TARGET = {
    "no_email": "contact", "no_phone": "contact", "no_name": "contact", "contact_placement": "contact",
    "no_summary": "summary",
    "no_experience": "experience", "no_dates": "experience", "few_bullets": "experience",
    "action_verbs": "experience", "quantify": "experience",
    "no_skills": "skills", "few_keywords": "skills",
    "no_education": "education", "degree": "education",
}


def _target(code: str, line: int, owners: list[dict[str, str]], resume: Resume) -> dict[str, str]:
    if 0 <= line < len(owners):
        return dict(owners[line])
    want = _CODE_TARGET.get(code)
    if want in ("contact", "summary"):
        return {"section": want, "entry": ""}
    if want:
        sec = next((s for s in resume.sections if s.kind == want), None)
        return {"section": sec.id if sec else f"new:{want}", "entry": ""}
    return {"section": "", "entry": ""}


def evaluate_text(text: str) -> dict[str, Any]:
    result = evaluate_ats(ats_parse(text))
    return {
        "score": round(result.score, 1),
        "grade": result.grade,
        "dimensions": [d.to_dict() for d in result.dimensions],
        "recommendations": [r.to_dict() for r in result.recommendations],
    }


def score_resume(resume: Resume) -> dict[str, Any]:
    """Score what an ATS will actually read: the canonical rendering of the document."""
    text, owners = render_with_map(resume)
    ats = evaluate_text(text) if text.strip() else {"score": 0.0, "grade": "Likely missed", "dimensions": [], "recommendations": []}
    for rec in ats["recommendations"]:
        rec["target"] = _target(rec["code"], rec.get("line", -1), owners, resume)
    return {
        "document": resume.to_dict(),
        "text": text,
        "owners": owners,
        "ats": ats,
        "ruleset": RULESET,
    }


def import_resume(data: bytes | None, filename: str, text: str | None) -> dict[str, Any]:
    if data:
        ex = extract_text(data, filename)
        raw, kind, notes = ex.text, ex.kind, ex.notes
    elif text and text.strip():
        raw, kind, notes = text, "text", []
    else:
        raise ValueError("Provide a resume file or paste resume text.")
    resume = parse_resume_text(raw)
    scored = score_resume(resume)
    scored["source"] = {"kind": kind, "notes": notes, "filename": filename or ""}
    # What the file looked like to a parser *before* cleanup.
    scored["original"] = evaluate_text(raw)
    scored["original_text"] = raw
    return scored
