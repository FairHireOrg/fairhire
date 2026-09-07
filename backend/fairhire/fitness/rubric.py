"""Build an explainable ATS-parsability report from deterministic evidence.

The score measures how cleanly an ATS / parser can read the *resume*. The job
description is used only as a relevance vector (which concepts it asks for) to
surface keyword presence — it never drives the score. Everything is computed with
exact rules, so identical input always yields an identical score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fairhire.config import Config
from fairhire.fitness import ats
from fairhire.fitness.extract import ResumeFeatures, extract_resume_features
from fairhire.fitness.hybrid import match_requirements
from fairhire.fitness.ner import parse_job_description, parse_resume
from fairhire.fitness.requirements import RULESET_VERSION, checklist_id, extract_checklist, validate_checklist

DISCLAIMER = (
    "This score measures how cleanly an ATS / parser can read your resume. It is "
    "not a hiring probability, a measure of ability, or a verdict on bias. The job "
    "description is only used to surface relevant keywords; it never affects the score."
)

StyleMode = str  # kept for API compatibility; scoring is a single deterministic mode


@dataclass
class FitnessReport:
    ats_score: float
    ats_grade: str
    extraction_status: str
    job_title: str | None
    dimensions: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    keyword_coverage: dict[str, int]
    keyword_groups: list[dict[str, Any]]
    resume_fields: dict[str, Any]
    sections_found: dict[str, bool]
    skills: list[str]
    resume_text: str
    job_description: str
    checklist_id: str
    ruleset_version: str
    ai_available: bool
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ats_score": self.ats_score,
            "ats_grade": self.ats_grade,
            "extraction_status": self.extraction_status,
            "job_title": self.job_title,
            "dimensions": self.dimensions,
            "recommendations": self.recommendations,
            "keyword_coverage": self.keyword_coverage,
            "keyword_groups": self.keyword_groups,
            "resume_fields": self.resume_fields,
            "sections_found": self.sections_found,
            "skills": self.skills,
            "resume_text": self.resume_text,
            "job_description": self.job_description,
            "checklist_id": self.checklist_id,
            "ruleset_version": self.ruleset_version,
            "ai_available": self.ai_available,
            "disclaimer": self.disclaimer,
            "scorable": bool(self.resume_text and self.resume_text.strip()),
        }


def _serializable_fields(resume) -> dict[str, Any]:
    fields = dict(resume.fields)
    if not isinstance(fields.get("titles"), list):
        fields["titles"] = []
    return fields


def score_resume(
    resume_text: str,
    job_description: str,
    style_mode: str = "balanced",
    config: Config | None = None,
    resume_features: ResumeFeatures | None = None,
    *,
    preextracted: bool = False,
    confirmations: dict[str, bool] | None = None,
    requirements: list[dict] | None = None,
) -> FitnessReport:
    del style_mode, preextracted, confirmations
    config = config or Config()
    resume = parse_resume(resume_text)
    jd = parse_job_description(job_description)

    # ---- ATS parsability: resume-only, deterministic ----
    result = ats.evaluate_ats(resume)

    # ---- JD as a relevance VECTOR (informational only, never scored) ----
    checklist = extract_checklist(jd) if requirements is None else validate_checklist(requirements, jd)
    hybrid = match_requirements(checklist, jd, resume, max_requirements=200)
    keyword_groups = [
        {
            "term": row.term,
            "kind": row.kind,
            "required": row.required,
            "matched": row.matched,
            "resume_term": row.resume_term,
        }
        for row in hybrid.rows
    ]
    keyword_coverage = {
        "matched": sum(1 for row in hybrid.rows if row.matched),
        "total": len(hybrid.rows),
    }

    res_f = resume_features or extract_resume_features(resume_text)
    skills = res_f.skills if isinstance(res_f.skills, list) else []

    return FitnessReport(
        ats_score=result.score,
        ats_grade=result.grade,
        extraction_status="deterministic_only" if requirements is None else "reviewed_checklist",
        job_title=jd.title,
        dimensions=[d.to_dict() for d in result.dimensions],
        recommendations=[r.to_dict() for r in result.recommendations],
        keyword_coverage=keyword_coverage,
        keyword_groups=keyword_groups,
        resume_fields=_serializable_fields(resume),
        sections_found=resume.sections,
        skills=skills,
        resume_text=resume.text,
        job_description=jd.text,
        checklist_id=checklist_id(checklist),
        ruleset_version=RULESET_VERSION,
        ai_available=config.llm_extraction_enabled,
        disclaimer=DISCLAIMER,
    )


# Back-compat alias
Blocker = Any
