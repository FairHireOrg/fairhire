"""Deterministic feature extraction facade.

Replaces the previous LLM-based extraction. Structured fields (email, phone,
dates, URLs, degrees) come from regex rules; skills/terms come from the
curated ontology matcher. Everything is exact and explainable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from fairhire.fitness import matcher, ner
from fairhire.fitness.ontology import category_label


@dataclass
class JDFeatures:
    role_title: str | None
    role_summary: str
    required_terms: list[dict[str, Any]] = field(default_factory=list)
    optional_terms: list[dict[str, Any]] = field(default_factory=list)
    source: str = "ner"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResumeFeatures:
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    degrees: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)
    source: str = "ner"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_jd_features(job_description: str) -> JDFeatures:
    doc = ner.parse_job_description(job_description)
    required_rows: list[dict[str, Any]] = []
    for t in doc.required_terms:
        occ = next((o for o in doc.occurrences if o.canonical == t), None)
        required_rows.append(
            {
                "term": t,
                "category": occ.category if occ else "other",
                "label": category_label(occ.category) if occ else "Other",
            }
        )
    optional_rows: list[dict[str, Any]] = []
    for t in doc.optional_terms:
        occ = next((o for o in doc.occurrences if o.canonical == t), None)
        optional_rows.append(
            {
                "term": t,
                "category": occ.category if occ else "other",
                "label": category_label(occ.category) if occ else "Other",
            }
        )

    role_summary = _jd_summary(doc)
    return JDFeatures(
        role_title=doc.title,
        role_summary=role_summary,
        required_terms=required_rows,
        optional_terms=optional_rows,
    )


def _jd_summary(doc: ner.ParsedDoc) -> str:
    """Deterministic one-line summary of the JD's top required skills."""
    tops = doc.required_terms[:6]
    if not tops:
        return "No explicit required skills detected."
    return "Requires: " + ", ".join(tops) + "."


def extract_resume_features(resume_text: str) -> ResumeFeatures:
    doc = ner.parse_resume(resume_text)
    fields = doc.fields

    def s(key: str) -> str | None:
        val = fields.get(key)
        return val if isinstance(val, str) and val else None

    skills: list[str] = []
    seen: set[str] = set()
    for occ in doc.occurrences:
        if occ.canonical not in seen:
            seen.add(occ.canonical)
            skills.append(occ.canonical)
        if len(skills) >= 24:
            break

    titles = fields.get("titles") or []
    if not isinstance(titles, list):
        titles = []
    degrees = fields.get("degrees") or []
    if not isinstance(degrees, list):
        degrees = []

    return ResumeFeatures(
        name=None,
        email=s("email"),
        phone=s("phone"),
        location=s("location"),
        linkedin=s("linkedin"),
        github=s("github"),
        degrees=degrees,
        titles=titles,
        skills=skills,
        sections_found=[k for k, v in doc.sections.items() if v],
    )


def match_documents(jd_text: str, resume_text: str) -> tuple[ner.ParsedDoc, ner.ParsedDoc, matcher.MatchResult]:
    jd = ner.parse_job_description(jd_text)
    resume = ner.parse_resume(resume_text)
    result = matcher.match_documents(jd, resume)
    return jd, resume, result
