"""Deterministic ATS-parsability evaluation of a resume.

The job description is used only as a *relevance vector* (which concepts it asks
for); it never drives the score. The score measures how cleanly an ATS / parser
can read the resume:

  * contact block (email, phone, location, professional links, name)
  * standard section headings (summary, experience, education, skills, projects)
  * chronological experience (roles with visible date ranges)
  * education (degree + institution)
  * a keyword-rich, machine-readable skills section
  * scannable bullets (action verbs, quantified outcomes)

Everything is computed from the parsed resume with exact rules, so identical
input always yields an identical score.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fairhire.fitness.ner import ParsedDoc

# Section-heading aliases that matter most for parsing (from sections.py).
_CORE_SECTIONS = ("summary", "experience", "skills", "education")
_BONUS_SECTIONS = ("projects", "publications", "certifications")

_CONTACT_RE = {
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"),
    "linkedin": re.compile(r"linkedin\.com[/\w.@-]+", re.I),
    "github": re.compile(r"github\.com[/\w.@-]+", re.I),
    "url": re.compile(r"https?://[^\s]+|www\.[^\s]+"),
}
_ACTION_RE = re.compile(
    r"\b(built|designed|developed|led|owned|created|implemented|shipped|"
    r"launched|optimized|authored|integrated|evaluated|taught|coordinated|"
    r"reduced|improved|automated|refactored|scaled)\b",
    re.I,
)
_IMPACT_RE = re.compile(
    r"(\d+\s*%|\d+\s*\+|\d+\s*x\b|\$\s?\d|\d+\s*(?:users|students|sessions|"
    r"packets|events|requests|repos|files)(?:\s*per\s*[a-z]+)?|millions?|thousands?)",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*(?:[-*•·▪◦‣]|\d+[.)])\s*")


@dataclass
class AtsDimension:
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
class AtsRecommendation:
    severity: str
    code: str
    title: str
    detail: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "action": self.action,
        }


@dataclass
class AtsResult:
    score: float
    grade: str
    dimensions: list[AtsDimension]
    recommendations: list[AtsRecommendation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "grade": self.grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


def _grade(score: float) -> str:
    if score >= 80:
        return "Strong"
    if score >= 55:
        return "Good"
    if score >= 35:
        return "Needs work"
    return "Likely missed"


def _detect_name(text: str) -> str | None:
    """Low-risk heuristic: first short, capitalized, punctuation-light line."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _CONTACT_RE["email"].search(line) or _CONTACT_RE["url"].search(line):
            continue
        if len(line) > 40 or len(line.split()) > 5:
            continue
        letters = re.sub(r"[^A-Za-z ]", "", line)
        if not letters.strip():
            continue
        if letters.strip().istitle() and not re.search(r"[,.]$", line):
            return line
    return None


def evaluate_ats(resume: ParsedDoc) -> AtsResult:
    text = resume.text
    fields = resume.fields
    sections = resume.sections
    body = resume

    # ---- Contact block ----
    contact_evidence: list[str] = []
    contact_present = 0
    contact_total = 0
    if fields.get("email"):
        contact_present += 1
        contact_evidence.append("email")
    contact_total += 1
    if fields.get("phone"):
        contact_present += 1
        contact_evidence.append("phone")
    contact_total += 1
    if fields.get("location"):
        contact_present += 1
        contact_evidence.append("location")
    contact_total += 1
    if fields.get("linkedin") or fields.get("github"):
        contact_present += 1
        contact_evidence.append("linkedin/github")
    contact_total += 1
    name = _detect_name(text)
    if name:
        contact_present += 1
        contact_evidence.append("name")
    contact_total += 1
    contact_score = 100.0 * (contact_present / contact_total)

    # ---- Section headings ----
    sec_present = [k for k in _CORE_SECTIONS if sections.get(k)]
    sec_bonus = [k for k in _BONUS_SECTIONS if sections.get(k)]
    sec_score = 100.0 * (
        (len(sec_present) / len(_CORE_SECTIONS)) * 0.8
        + (len(sec_bonus) / 3) * 0.2
    )

    # ---- Chronology ----
    date_ranges = fields.get("date_ranges") or []
    if not isinstance(date_ranges, list):
        date_ranges = []
    titles = fields.get("titles") or []
    if not isinstance(titles, list):
        titles = []
    role_strength = 0
    if len(titles) >= 1:
        role_strength += 1
    if len(date_ranges) >= 1:
        role_strength += 1
    if len(titles) >= 2:
        role_strength += 1
    chrono_score = 100.0 * (role_strength / 3)

    # ---- Education ----
    degrees = fields.get("degrees") or []
    if not isinstance(degrees, list):
        degrees = []
    edu_present = 0
    edu_total = 2
    edu_evidence: list[str] = []
    if degrees:
        edu_present += 1
        edu_evidence.append("degree")
    if re.search(r"\b(?:university|college|institute|institut|school)\b", text, re.I):
        edu_present += 1
        edu_evidence.append("institution")
    edu_score = 100.0 * (edu_present / edu_total)

    # ---- Keywords / skills section ----
    # Skills are surfaced from ontology occurrences anywhere in the resume;
    # a dedicated Skills section is the strongest ATS keyword signal.
    occurrences = body.occurrences
    skill_terms: list[str] = []
    seen: set[str] = set()
    for occ in occurrences:
        if occ.canonical not in seen:
            seen.add(occ.canonical)
            skill_terms.append(occ.canonical)
    categories = {occ.category for occ in occurrences}
    kw_score = 0.0
    if sections.get("skills"):
        kw_score += 40.0
    if len(skill_terms) >= 5:
        kw_score += 40.0
    elif len(skill_terms) >= 3:
        kw_score += 20.0
    if len(categories) >= 3:
        kw_score += 10.0
    else:
        kw_score += 0.0
    if len(occurrences) >= 8:
        kw_score += 10.0
    kw_score = min(100.0, kw_score)

    # ---- Scannable experience (bullets) ----
    lines = [ln for ln in text.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if _BULLET_RE.match(ln)]
    action_hits = sum(1 for b in bullets if _ACTION_RE.search(b))
    impact_hits = sum(1 for b in bullets if _IMPACT_RE.search(b))
    exp_score = 0.0
    if len(bullets) >= 3:
        exp_score += 40.0
    elif len(bullets) >= 1:
        exp_score += 20.0
    if action_hits >= 2:
        exp_score += 30.0
    else:
        exp_score += min(15.0, action_hits * 7.5)
    exp_score += min(30.0, (impact_hits / max(len(bullets), 1)) * 60)

    # ---- Text extraction quality ----
    if not text:
        text_score = 0.0
    else:
        alnum = sum(1 for c in text if c.isalnum())
        ratio = alnum / len(text)
        length = len(text)
        quality = 0.0
        if ratio >= 0.85:
            quality += 50.0
        elif ratio >= 0.6:
            quality += 25.0
        if 200 <= length <= 5000:
            quality += 50.0
        elif length > 5000:
            quality += 25.0
        text_score = quality

    dims = [
        AtsDimension("sections", "Section structure", sec_score, 0.25,
                     f"Headings found: {', '.join(sec_present + sec_bonus) or 'none'}. ATS parsers rely on clear headings.", sec_present + sec_bonus),
        AtsDimension("contact", "Contact block", contact_score, 0.15,
                     f"{len(contact_evidence)} contact signals: {', '.join(contact_evidence) or 'none detected'}.", contact_evidence),
        AtsDimension("chronology", "Chronological experience", chrono_score, 0.15,
                     f"{len(titles)} role title(s), {len(date_ranges)} date range(s).", titles[:4]),
        AtsDimension("keywords", "Keyword-rich skills", kw_score, 0.15,
                     f"{len(skill_terms)} recognized technologies across {len(categories)} categories.", skill_terms[:8]),
        AtsDimension("education", "Education", edu_score, 0.10,
                     f"{', '.join(edu_evidence) or 'no degree or institution detected'}.", edu_evidence),
        AtsDimension("achievements", "Scannable bullets", exp_score, 0.15,
                     f"{len(bullets)} bullets, {action_hits} action verbs, {impact_hits} quantified outcomes.", bullets[:5]),
        AtsDimension("text", "Text extraction", text_score, 0.05,
                     "Indicates whether the document text extracts cleanly (layout, images, tables).", []),
    ]
    weight_sum = sum(d.weight for d in dims)
    score = sum(d.score * d.weight for d in dims) / weight_sum
    scorable = bool(text and scores_nonzero(dims))
    if not scorable:
        score = 0.0

    recs = _recommendations(text, fields, sections, sec_present, titles, date_ranges,
                            degrees, bullets, skill_terms, contact_evidence, name,
                            chronological=(len(date_ranges) >= 1))

    return AtsResult(score=score, grade=_grade(score), dimensions=dims, recommendations=recs)


def scores_nonzero(dims: list[AtsDimension]) -> bool:
    return any(d.score > 0 for d in dims)


def _recommendations(
    text: str,
    fields: dict[str, Any],
    sections: dict[str, bool],
    sec_present: list[str],
    titles: list[str],
    date_ranges: list[str],
    degrees: list[str],
    bullets: list[str],
    skill_terms: list[str],
    contact: list[str],
    name: str | None,
    *,
    chronological: bool,
) -> list[AtsRecommendation]:
    recs: list[AtsRecommendation] = []

    def add(sev: str, code: str, title: str, detail: str, action: str) -> None:
        recs.append(AtsRecommendation(sev, code, title, detail, action))

    if not text or len(text) < 200:
        add("high", "text_extract", "Text extraction looks weak",
            "Very little text was read from the document.",
            "Ensure the resume is a text-based PDF (not an image scan). Avoid tables, text boxes, and header/footer-only layouts.")
    if "email" not in contact:
        add("high", "no_email", "Add a plain-text email",
            "ATS parsers match candidates by email; none was found.",
            "Put a single email address in the contact line.")
    if "phone" not in contact:
        add("high", "no_phone", "Add a phone number",
            "No phone number was detected.",
            "Add a phone number in a standard format, e.g. (555) 123-4567.")
    if "summary" not in sec_present:
        add("low", "no_summary", "Add a short Summary",
            "No Summary/Profile heading was found.",
            "Add a 2–3 line professional summary under a clear 'Summary' heading.")
    if "experience" not in sec_present:
        add("high", "no_experience", "Add an Experience section",
            "No Experience/Employment heading was detected.",
            "Add a clearly headed 'Experience' section with roles and dates.")
    elif not chronological:
        add("medium", "no_dates", "Add date ranges to your roles",
            "Experience was found but no work date ranges were detected.",
            "Format each role as 'Title | Company | MONTH YEAR – MONTH YEAR'.")
    if "skills" not in sec_present:
        add("high", "no_skills", "Add a dedicated Skills section",
            "ATS systems search a Skills section for keywords.",
            "Add a 'Skills' heading followed by a comma-separated list of technologies.")
    elif len(skill_terms) < 5:
        add("medium", "few_keywords", "Name more technologies",
            "Fewer than 5 recognizable technologies were tagged.",
            "List the concrete languages/frameworks/tools you use.")
    if "education" not in sec_present:
        add("medium", "no_education", "Add an Education section",
            "No Education heading was detected.",
            "Add an 'Education' section with your degree and institution.")
    elif not degrees:
        add("medium", "degree", "State your degree",
            "Education present but no degree was detected.",
            "Write the full degree, e.g. 'B.S. Computer Science'.")
    action_hits = sum(1 for b in bullets if _ACTION_RE.search(b))
    impact_hits = sum(1 for b in bullets if _IMPACT_RE.search(b))
    if len(bullets) < 3:
        add("medium", "few_bullets", "Use scannable bullets",
            "Experience has few bullet points.",
            "Break each role into 3–5 short bullets starting with an action verb.")
    elif action_hits < 2:
        add("low", "action_verbs", "Start bullets with action verbs",
            "Most bullets do not begin with a strong action verb.",
            "Reword bullets to start with verbs like 'Built', 'Launched', 'Reduced'.")
    if impact_hits == 0:
        add("medium", "quantify", "Add measurable outcomes",
            "No quantified results were detected.",
            "Where honest, add numbers: 'cut build time 30%', 'handled 1M requests/day'.")
    if not name:
        add("medium", "no_name", "Add your name as the header",
            "A readable full name was not detected at the top.",
            "Put your name as the very first line, then city/state, then contact details.")

    order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: order[r.severity])
    return recs[:10]
