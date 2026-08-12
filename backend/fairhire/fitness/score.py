"""Deterministic fitness scoring.

Every dimension is a weighted, rule-based calculation. Works with any
requirement list (ontology terms from the pure deterministic path, or
LLM-extracted requirement rows from the hybrid path) — scoring itself never
changes and never depends on an LLM.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from fairhire.fitness.ner import ParsedDoc

_IMPACT_RE = re.compile(
    r"(\d+\s*%|\d+\s*\+|\d+\s*x\b|\$\s?\d|millions?|thousands?|"
    r"\b(shipped|built|launched|authored|led|owned|created|published)\b)",
    re.I,
)
_ACTION_RE = re.compile(
    r"\b(built|designed|developed|led|owned|created|implemented|shipped|"
    r"launched|optimized|authored|integrated|evaluated|taught|coordinated)\b",
    re.I,
)

DIMENSION_WEIGHTS = {
    "required_skills": 0.55,
    "optional_skills": 0.10,
    "structure": 0.15,
    "experience_depth": 0.20,
}


class RequirementRow(Protocol):
    term: str
    required: bool
    matched: bool
    score: float
    kind: str


@dataclass
class Dimension:
    key: str
    label: str
    score: float
    weight: float
    detail: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "score": round(self.score, 1),
            "weight": self.weight,
            "detail": self.detail,
            "evidence": self.evidence,
        }


@dataclass
class Blockers:
    severity: str
    code: str
    message: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def _requirements_score(
    rows: Sequence[RequirementRow], label: str
) -> tuple[float, str, list[str]]:
    if not rows:
        return 0.0, f"No {label.lower()} requirements detected.", []
    matched_rows = [r for r in rows if r.matched]
    matched = len(matched_rows)
    total = len(rows)
    rate = matched / total
    quality_avg = sum(r.score for r in matched_rows) / total if matched_rows else 0.0
    score = 100.0 * (0.7 * rate + 0.3 * quality_avg)
    detail = f"{matched}/{total} {label.lower()} found (avg match quality {quality_avg:.2f})."
    return round(score, 1), detail, [r.term for r in matched_rows]


def _structure_score(resume: ParsedDoc) -> tuple[float, str, list[str]]:
    fields = resume.fields
    present: list[str] = []

    if fields.get("email"):
        present.append("email")
    if fields.get("phone"):
        present.append("phone")
    if fields.get("linkedin"):
        present.append("LinkedIn")
    if fields.get("github"):
        present.append("GitHub")
    if fields.get("degrees"):
        present.append("degree")
    if resume.sections.get("experience") or resume.sections.get("projects"):
        present.append("work/project history")
    if resume.sections.get("education"):
        present.append("education section")
    if resume.sections.get("skills"):
        present.append("skills section")
    if fields.get("date_ranges"):
        present.append("date ranges")

    total = 8
    score = min(100.0, 100.0 * len(present) / total)
    detail = f"{len(present)}/{total} parseable structures found: {', '.join(present) or 'none'}."
    return round(score, 1), detail, present


def _experience_depth_score(resume: ParsedDoc) -> tuple[float, str, list[str]]:
    lines = [ln.strip() for ln in resume.text.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if ln[:1] in {"-", "*", "•"} or re.match(r"^–\s+", ln)]
    corpus = bullets if bullets else [ln for ln in lines if 40 <= len(ln) <= 220][:40]
    if not corpus:
        return 15.0, "Little accomplishment language detected.", []

    impact_hits = sum(1 for b in corpus if _IMPACT_RE.search(b))
    action_hits = sum(1 for b in corpus if _ACTION_RE.search(b))
    impact_ratio = min(1.0, impact_hits / max(len(corpus), 1))
    action_ratio = min(1.0, action_hits / max(len(corpus), 1))

    score = 100.0 * (0.6 * impact_ratio + 0.4 * action_ratio)
    bonus = 0.0
    if resume.sections.get("projects"):
        bonus += 10.0
    if resume.sections.get("publications"):
        bonus += 5.0
    score = min(100.0, score + bonus)

    detail = (
        f"{impact_hits} quantified outcomes and {action_hits} ownership verbs "
        f"across {len(corpus)} lines"
        + ("; projects section present" if resume.sections.get("projects") else "")
        + ("; publications present" if resume.sections.get("publications") else "")
        + "."
    )
    evidence = [b[:140] for b in corpus if _IMPACT_RE.search(b)][:5]
    return round(score, 1), detail, evidence


def compute_score(
    requirements: Sequence[RequirementRow],
    resume: ParsedDoc,
) -> tuple[float, list[Dimension], list[Blockers]]:
    required_rows = [r for r in requirements if r.required]
    optional_rows = [r for r in requirements if not r.required]

    dims: list[Dimension] = []
    req_score, req_detail, req_ev = _requirements_score(required_rows, "required skills")
    opt_score, opt_detail, opt_ev = _requirements_score(optional_rows, "nice-to-have skills")
    struct_score, struct_detail, struct_ev = _structure_score(resume)
    exp_score, exp_detail, exp_ev = _experience_depth_score(resume)

    dims = [
        Dimension("required_skills", "Required skills", req_score, DIMENSION_WEIGHTS["required_skills"], req_detail, req_ev),
        Dimension("optional_skills", "Nice-to-have skills", opt_score, DIMENSION_WEIGHTS["optional_skills"], opt_detail, opt_ev),
        Dimension("structure", "Structure", struct_score, DIMENSION_WEIGHTS["structure"], struct_detail, struct_ev),
        Dimension("experience_depth", "Experience depth", exp_score, DIMENSION_WEIGHTS["experience_depth"], exp_detail, exp_ev),
    ]

    overall = sum(d.score * d.weight for d in dims)

    blockers: list[Blockers] = []
    missing = [r.term for r in required_rows if not r.matched]
    if missing:
        blockers.append(
            Blockers(
                "high" if len(missing) >= 3 else "medium",
                "missing_required",
                "Required items not found: " + ", ".join(missing[:8]),
                "Add honest evidence for these items, or tailor the resume to this role.",
            )
        )
    if not resume.sections.get("experience") and not resume.sections.get("projects"):
        blockers.append(
            Blockers(
                "high",
                "missing_work_signal",
                "No Experience or Projects section detected.",
                "Add concrete work or shipped projects.",
            )
        )
    if not resume.fields.get("email"):
        blockers.append(
            Blockers(
                "medium",
                "missing_contact",
                "No email address found in the resume.",
                "Add your email so recruiters can reach you.",
            )
        )
    if overall < 40:
        blockers.append(
            Blockers(
                "medium",
                "low_overall",
                "Overall deterministic score is low for this JD.",
                "Prioritize the missing required items and add quantified outcomes.",
            )
        )

    order = {"high": 0, "medium": 1, "low": 2}
    blockers.sort(key=lambda b: order[b.severity])
    return round(overall, 1), dims, blockers[:6]
