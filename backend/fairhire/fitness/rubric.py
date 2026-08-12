"""Resume–JD fitness report.

Pipeline:
  1. Deterministic NER parse of both documents (always).
  2. Optional DeepSeek extraction of *structured requirements* (hybrid mode)
     when a key is configured — covers soft skills, degrees, years, abilities.
  3. Deterministic matching of every requirement (ontology tiers / containment /
     regex) -> links with exact spans.
  4. Weighted, explainable scoring.

The LLM only chooses what to look for; it never decides whether a match exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fairhire.config import Config
from fairhire.fitness.extract import (
    JDFeatures,
    ResumeFeatures,
    extract_jd_features,
    extract_resume_features,
)
from fairhire.fitness.hybrid import HybridResult, RequirementMatchRow, match_requirements
from fairhire.fitness.matcher import MatchResult, match_documents
from fairhire.fitness.ner import ParsedDoc, parse_job_description, parse_resume
from fairhire.fitness.score import Blockers, Dimension, compute_score

StyleMode = str  # kept for API compatibility; scoring is a single deterministic mode

DISCLAIMER = (
    "FairHire scores fit with deterministic rules: NER-style term matching over "
    "a curated skill ontology plus regex rules for structured fields. When a "
    "DeepSeek key is configured, it only extracts structured requirements "
    "(soft skills, degrees, years) — matching and scoring stay deterministic "
    "and explainable."
)

MODE_LABEL = {
    "hybrid": "hybrid (DeepSeek extraction)",
    "deterministic": "deterministic (no LLM)",
}


@dataclass
class FitnessReport:
    overall_score: float
    extraction_mode: str
    job_title: str | None
    dimensions: list[Dimension]
    blockers: list[Blockers]
    links: list[dict[str, Any]]
    required_terms: list[dict[str, Any]]
    optional_terms: list[dict[str, Any]]
    missing_required: list[str]
    missing_optional: list[str]
    jd_sentences: list[dict[str, Any]]
    resume_sentences: list[dict[str, Any]]
    resume_fields: dict[str, Any]
    resume_titles: list[str]
    sections_found: dict[str, bool]
    resume_char_count: int
    jd_features: dict[str, Any]
    resume_features: dict[str, Any]
    disclaimer: str
    resume_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "extraction_mode": self.extraction_mode,
            "job_title": self.job_title,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "blockers": [b.to_dict() for b in self.blockers],
            "links": self.links,
            "required_terms": self.required_terms,
            "optional_terms": self.optional_terms,
            "missing_required": self.missing_required,
            "missing_optional": self.missing_optional,
            "jd_sentences": self.jd_sentences,
            "resume_sentences": self.resume_sentences,
            "resume_fields": self.resume_fields,
            "resume_titles": self.resume_titles,
            "sections_found": self.sections_found,
            "resume_char_count": self.resume_char_count,
            "jd_features": self.jd_features,
            "resume_features": self.resume_features,
            "disclaimer": self.disclaimer,
            "resume_text": self.resume_text,
        }


def _sentence_dicts(doc: ParsedDoc) -> list[dict[str, Any]]:
    return [
        {"index": s.index, "text": s.text, "start": s.start, "end": s.end}
        for s in doc.sentences
    ]


def _rows_to_terms(rows: list[RequirementMatchRow]) -> list[dict[str, Any]]:
    return [r.to_dict() for r in rows]


def _deterministic_rows(
    jd: ParsedDoc, match: MatchResult
) -> tuple[list[RequirementMatchRow], list[str], list[str]]:
    link_by_canonical = {lnk.canonical: lnk for lnk in match.links}
    required: list[RequirementMatchRow] = []
    for term in jd.required_terms:
        lnk = link_by_canonical.get(term)
        required.append(
            RequirementMatchRow(
                term=term,
                kind="skill",
                required=True,
                matched=lnk is not None,
                quality=lnk.quality if lnk else None,
                score=lnk.score if lnk else 0.0,
                resume_term=lnk.resume_term if lnk else None,
            )
        )
    optional: list[RequirementMatchRow] = []
    for term in jd.optional_terms:
        lnk = link_by_canonical.get(term)
        optional.append(
            RequirementMatchRow(
                term=term,
                kind="skill",
                required=False,
                matched=lnk is not None,
                quality=lnk.quality if lnk else None,
                score=lnk.score if lnk else 0.0,
                resume_term=lnk.resume_term if lnk else None,
            )
        )
    return required + optional, list(match.missing_required), list(match.missing_optional)


def score_resume(
    resume_text: str,
    job_description: str,
    style_mode: StyleMode = "balanced",
    config: Config | None = None,
    jd_features: JDFeatures | None = None,
    resume_features: ResumeFeatures | None = None,
    *,
    preextracted: bool = False,
) -> FitnessReport:
    del style_mode, preextracted
    config = config or Config()

    jd = parse_job_description(job_description)
    resume = parse_resume(resume_text)

    rows: list[RequirementMatchRow] = []
    links: list[dict[str, Any]] = []
    missing_required: list[str] = []
    missing_optional: list[str] = []
    mode = "deterministic"
    llm_evidence = None

    if config.llm_extraction_enabled:
        from fairhire.fitness.llm_extract import extract_requirements, extract_resume_evidence

        requirements = extract_requirements(job_description, config)
        llm_evidence = extract_resume_evidence(resume_text, config)
        if requirements:
            hybrid: HybridResult = match_requirements(requirements, jd, resume, llm_evidence)
            rows = hybrid.rows
            links = [lnk.to_dict() for lnk in hybrid.links]
            missing_required = list(hybrid.missing_required)
            missing_optional = list(hybrid.missing_optional)
            mode = "hybrid"

    if not rows:
        match = match_documents(jd, resume)
        rows, missing_required, missing_optional = _deterministic_rows(jd, match)
        links = [lnk.to_dict() for lnk in match.links]

    overall, dims, blockers = compute_score(rows, resume)

    jd_f = jd_features or extract_jd_features(job_description)
    res_f = resume_features or extract_resume_features(resume_text)
    if mode == "hybrid" and llm_evidence is not None:
        _merge_evidence(res_f, llm_evidence)

    resume_titles = res_f.titles
    if not resume_titles:
        titles = resume.fields.get("titles") or []
        resume_titles = titles if isinstance(titles, list) else []

    required_rows = [r for r in rows if r.required]
    optional_rows = [r for r in rows if not r.required]

    return FitnessReport(
        overall_score=overall,
        extraction_mode=mode,
        job_title=jd.title or jd_f.role_title,
        dimensions=dims,
        blockers=blockers,
        links=links,
        required_terms=_rows_to_terms(required_rows),
        optional_terms=_rows_to_terms(optional_rows),
        missing_required=missing_required,
        missing_optional=missing_optional,
        jd_sentences=_sentence_dicts(jd),
        resume_sentences=_sentence_dicts(resume),
        resume_fields=_serializable_fields(resume),
        resume_titles=resume_titles,
        sections_found=resume.sections,
        resume_char_count=len(resume.text),
        jd_features=jd_f.to_dict(),
        resume_features=res_f.to_dict(),
        disclaimer=DISCLAIMER,
        resume_text=resume.text,
    )


def _merge_evidence(res_f: ResumeFeatures, evidence: Any) -> None:
    if not res_f.degrees and evidence.degree:
        res_f.degrees = [evidence.degree]
    existing = {s.lower() for s in res_f.skills}
    for skill in evidence.skills or []:
        if skill.lower() not in existing:
            res_f.skills.append(skill)
    res_f.skills = res_f.skills[:24]


def _serializable_fields(resume: ParsedDoc) -> dict[str, Any]:
    fields = dict(resume.fields)
    titles = fields.get("titles")
    if not isinstance(titles, list):
        fields["titles"] = []
    return fields


# Back-compat alias
Blocker = Blockers
