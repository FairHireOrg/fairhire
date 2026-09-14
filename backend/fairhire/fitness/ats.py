"""Deterministic ATS-parsability evaluation of a resume.

The job description is used only as a *relevance vector* (which concepts it asks
for); it never drives the score. The score measures how cleanly an ATS / parser
can read the resume, along two weighted families (still fully deterministic):

Parser-safe structure (~55%) — classic article failure modes:

  * layout (single column vs multi-column / wide-gap scramble)
  * contact placement (name/email/phone in the first ~15 body lines)
  * section labels (core headings match a whitelist; creative ones flagged)
  * date consistency (``Month YYYY`` preferred; mixed formats penalized)
  * bullet style (plain ``-`` / ``•`` / digits; decorative glyphs penalized)
  * text integrity (alphanumeric ratio / plausible length)

Field-extraction quality (~45%):

  * contact completeness (email, phone, location, link, name)
  * chronology (titles + date ranges)
  * education (degree + institution)
  * skills section (dedicated Skills heading + bare-token density, not raw
    ontology hit-count alone)
  * achievements (bullets with action verbs / quantified outcomes)

Every failing check emits an ``AtsRecommendation`` with ``code``, ``action``
and **character offsets / line refs** so the editor can jump to the problem.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fairhire.fitness.lexicon import role_words_pattern, section_aliases
from fairhire.fitness.ner import DEGREE_RE, MONTHS, ParsedDoc
from fairhire.fitness.sections import _is_heading, _normalize_heading

# Section-heading aliases that matter most for parsing (from sections.py data).
_CORE_SECTIONS = ("summary", "experience", "skills", "education")
_BONUS_SECTIONS = ("projects", "publications", "certifications")

# Parser-safe dimension weights: structure family sums to 0.55, extraction to 0.45.
_STRUCTURE_WEIGHTS = {
    "layout": 0.12,
    "contact_placement": 0.08,
    "headings": 0.12,
    "date_format": 0.08,
    "bullet_style": 0.07,
    "text_integrity": 0.08,
}
_EXTRACTION_WEIGHTS = {
    "contact": 0.10,
    "chronology": 0.10,
    "education": 0.07,
    "skills": 0.10,
    "achievements": 0.08,
}

_CONTACT_LINES = 15  # body lines ATS parsers scan for the contact block

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
    r"(\d+\s*%|\d+\s*[KkMm]?\s*\+|\d+\s*x\b|\$\s?\d|\d+\s*(?:users|students|sessions|"
    r"packets|events|requests|repos|files)(?:\s*per\s*[a-z]+)?|millions?|thousands?)",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*(?:[-*•·▪◦‣]|\d+[.)])\s*")
_PLAIN_BULLET_LEADS = {"-", "*", "•", "·", "▪", "◦", "‣"}
# Punctuation that may legitimately start a line without being a bullet.
_NON_BULLET_LEADS = set("()[]\"'#/\\|<>+=~_&@$%^`:;,._?!")
_MONTH_YEAR_RE = re.compile(rf"\b{MONTHS}\s+(?:19|20)\d{{2}}\b", re.I)
_NUMERIC_DATE_RE = re.compile(r"\b(?:(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}|(?:19|20)\d{2}[/\-](?:0?[1-9]|1[0-2]))\b")
_BARE_RANGE_RE = re.compile(
    r"\b(?:19|20)\d{2}\s*(?:[-–—]|to)\s*(?:(?:19|20)\d{2}|Present|Current|Now)\b", re.I
)
_WIDE_GAP_RE = re.compile(r"\S(?: {3,}|\t+)\S")
_INSTITUTION_RE = re.compile(r"\b(?:university|college|institute|institut|school)\b", re.I)


@dataclass
class AtsDimension:
    key: str
    label: str
    score: float
    weight: float
    detail: str
    evidence: list[str] = field(default_factory=list)
    family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "score": round(self.score, 1),
            "weight": self.weight,
            "detail": self.detail,
            "evidence": self.evidence,
            "family": self.family,
        }


@dataclass
class AtsRecommendation:
    severity: str
    code: str
    title: str
    detail: str
    action: str
    start: int = -1
    end: int = -1
    line: int = -1

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "action": self.action,
            "start": self.start,
            "end": self.end,
            "line": self.line,
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


def _line_spans(text: str) -> list[tuple[int, str]]:
    """(absolute start offset, line text without newline) per physical line."""
    spans: list[tuple[int, str]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        spans.append((offset, line))
        offset += len(raw)
    return spans


def _line_of(spans: list[tuple[int, str]], offset: int) -> int:
    """1-based line number containing offset, or -1."""
    for i, (start, line) in enumerate(spans):
        if start <= offset < start + max(len(line), 1):
            return i + 1
    return -1


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


def _nonempty_lines(text: str) -> list[tuple[int, str]]:
    return [(start, line) for start, line in _line_spans(text) if line.strip()]


def _creative_headings(text: str) -> list[tuple[int, str]]:
    """Heading-shaped lines that match no whitelisted section alias.

    Skips the contact block (name/email/phone/URL lines) and any line with
    digits — real headings almost never contain them, while role and
    education lines often look title-cased.
    """
    aliases = section_aliases()
    known = {a for group in aliases.values() for a in group}
    name = _detect_name(text)
    role_re = role_words_pattern()
    out: list[tuple[int, str]] = []
    for start, line in _line_spans(text):
        stripped = line.strip()
        if not stripped or not _is_heading(line):
            continue
        if _CONTACT_RE["email"].search(stripped) or _CONTACT_RE["phone"].search(stripped):
            continue
        if _CONTACT_RE["url"].search(stripped):
            continue
        if name and stripped == name:
            continue
        if re.search(r"\d", stripped):
            continue
        # Education content (degree / institution) and bare role-title lines
        # often look title-cased; they are content, not headings.
        if DEGREE_RE.search(stripped) or _INSTITUTION_RE.search(stripped):
            continue
        if role_re.search(stripped):
            continue
        if _normalize_heading(line.rstrip(":")) not in known:
            out.append((start, stripped))
    return out


def _decorative_bullet_lines(text: str) -> list[tuple[int, str]]:
    """Bullet-intended lines using arrows/checkmarks/emoji instead of plain marks."""
    out: list[tuple[int, str]] = []
    for start, line in _line_spans(text):
        stripped = line.lstrip()
        if not stripped or _BULLET_RE.match(line):
            continue
        first = stripped[0]
        if first.isalnum() or first in _PLAIN_BULLET_LEADS or first in _NON_BULLET_LEADS:
            continue
        if len(stripped) > 2:  # ignore stray glyph-only lines
            out.append((start, line.strip()))
    return out


def _plain_bullets(text: str) -> list[tuple[int, str]]:
    return [(s, ln) for s, ln in _line_spans(text) if ln.strip() and _BULLET_RE.match(ln)]


def _date_formats(text: str) -> dict[str, list[tuple[int, int]]]:
    found: dict[str, list[tuple[int, int]]] = {"month_year": [], "numeric": [], "bare_range": []}
    for m in _MONTH_YEAR_RE.finditer(text):
        found["month_year"].append((m.start(), m.end()))
    occupied = [span for spans in found.values() for span in spans]
    for m in _NUMERIC_DATE_RE.finditer(text):
        if not any(s < m.end() and e > m.start() for s, e in occupied):
            found["numeric"].append((m.start(), m.end()))
    occupied = [span for spans in found.values() for span in spans]
    for m in _BARE_RANGE_RE.finditer(text):
        if not any(s < m.end() and e > m.start() for s, e in occupied):
            found["bare_range"].append((m.start(), m.end()))
    return {k: v for k, v in found.items() if v}


def evaluate_ats(resume: ParsedDoc) -> AtsResult:
    text = resume.text
    fields = resume.fields
    sections = resume.sections
    body = resume
    spans = _line_spans(text)
    nonempty = _nonempty_lines(text)

    # ================= Parser-safe structure (~55%) =================

    # ---- Layout: single column vs wide-gap scramble ----
    content_lines = [(s, ln) for s, ln in nonempty if len(ln.strip()) > 20]
    gap_lines = [(s, ln) for s, ln in content_lines if _WIDE_GAP_RE.search(ln)]
    gap_frac = len(gap_lines) / max(len(content_lines), 1)
    if gap_frac > 0.25:
        layout_score = 20.0
    elif gap_frac > 0.12:
        layout_score = 55.0
    elif gap_frac > 0.05:
        layout_score = 80.0
    else:
        layout_score = 100.0
    layout_evidence = [f"line {_line_of(spans, s)}" for s, _ in gap_lines[:5]]

    # ---- Contact placement: signals in the first body lines ----
    head_region = "\n".join(ln for _, ln in nonempty[:_CONTACT_LINES])
    head_start = nonempty[0][0] if nonempty else 0
    head_end = (nonempty[min(len(nonempty), _CONTACT_LINES) - 1][0]
                + len(nonempty[min(len(nonempty), _CONTACT_LINES) - 1][1])) if nonempty else 0
    placement_signals: list[str] = []
    if _CONTACT_RE["email"].search(head_region):
        placement_signals.append("email")
    if _CONTACT_RE["phone"].search(head_region):
        placement_signals.append("phone")
    if _detect_name(head_region):
        placement_signals.append("name")
    placement_score = {3: 100.0, 2: 65.0, 1: 35.0, 0: 10.0}[len(placement_signals)]

    # ---- Section labels: whitelist match + creative-heading flag ----
    sec_present = [k for k in _CORE_SECTIONS if sections.get(k)]
    sec_bonus = [k for k in _BONUS_SECTIONS if sections.get(k)]
    creative = _creative_headings(text)
    headings_score = 100.0 * ((len(sec_present) / len(_CORE_SECTIONS)) * 0.8 + (len(sec_bonus) / 3) * 0.2)
    if creative:
        headings_score = max(0.0, headings_score - min(30.0, 10.0 * len(creative)))

    # ---- Date consistency ----
    formats = _date_formats(text)
    active = set(formats)
    if not active:
        date_score = 35.0
    elif active == {"month_year"}:
        date_score = 100.0
    elif len(active) == 1:
        date_score = 70.0
    else:
        date_score = 40.0

    # ---- Bullet style ----
    plain = _plain_bullets(text)
    decorative = _decorative_bullet_lines(text)
    if decorative:
        bullet_style_score = 40.0
    elif plain:
        bullet_style_score = 100.0
    else:
        bullet_style_score = 50.0

    # ---- Text integrity (tightened) ----
    if not text:
        text_score = 0.0
    else:
        alnum = sum(1 for c in text if c.isalnum())
        ratio = alnum / len(text)
        length = len(text)
        if ratio >= 0.80:
            text_score = 50.0
        elif ratio >= 0.65:
            text_score = 30.0
        elif ratio >= 0.50:
            text_score = 10.0
        else:
            text_score = 0.0
        if 800 <= length <= 6000:
            text_score += 50.0
        elif 300 <= length < 800 or 6000 < length <= 9000:
            text_score += 30.0
        elif 200 <= length < 300:
            text_score += 15.0

    # ================= Field extraction quality (~45%) =================

    # ---- Contact completeness ----
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
    if _INSTITUTION_RE.search(text):
        edu_present += 1
        edu_evidence.append("institution")
    edu_score = 100.0 * (edu_present / edu_total)

    # ---- Skills section: dedicated heading + bare-token density ----
    occurrences = body.occurrences
    skill_terms: list[str] = []
    seen: set[str] = set()
    for occ in occurrences:
        if occ.canonical not in seen:
            seen.add(occ.canonical)
            skill_terms.append(occ.canonical)
    categories = {occ.category for occ in occurrences}
    skills_body = (resume.section_bodies or {}).get("skills", "") if hasattr(resume, "section_bodies") else ""
    bare_tokens = [
        tok.strip(" \t-•*·")
        for tok in re.split(r"[,;|\n]", skills_body)
        for tok in [tok.strip()]
        if len(tok.strip(" \t-•*·")) >= 2
    ]
    skills_score = 0.0
    if sections.get("skills"):
        skills_score += 40.0
    if len(bare_tokens) >= 8:
        skills_score += 35.0
    elif len(bare_tokens) >= 5:
        skills_score += 25.0
    elif len(bare_tokens) >= 3:
        skills_score += 12.0
    if len(categories) >= 3:
        skills_score += 15.0
    elif len(categories) >= 2:
        skills_score += 8.0
    if len(occurrences) >= 8:
        skills_score += 10.0
    skills_score = min(100.0, skills_score)

    # ---- Achievements: scannable bullets ----
    bullets = [ln for _, ln in plain]
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

    dims = [
        AtsDimension("layout", "Single-column layout", layout_score, _STRUCTURE_WEIGHTS["layout"],
                     f"{len(gap_lines)} of {len(content_lines)} content lines show wide interior gaps "
                     "(multi-column scramble). Single-column text parses reliably.",
                     layout_evidence, family="parser_safe"),
        AtsDimension("contact_placement", "Contact placement", placement_score,
                     _STRUCTURE_WEIGHTS["contact_placement"],
                     f"{len(placement_signals)} contact signals in the first {_CONTACT_LINES} body lines: "
                     f"{', '.join(placement_signals) or 'none'}. Parsers read the top first.",
                     placement_signals, family="parser_safe"),
        AtsDimension("headings", "Section labels", headings_score, _STRUCTURE_WEIGHTS["headings"],
                     f"Standard headings: {', '.join(sec_present + sec_bonus) or 'none'}. "
                     f"{len(creative)} creative heading(s) may confuse parsers.",
                     sec_present + sec_bonus, family="parser_safe"),
        AtsDimension("date_format", "Date consistency", date_score, _STRUCTURE_WEIGHTS["date_format"],
                     f"Date format(s) seen: {', '.join(sorted(active)) or 'none'}. "
                     "Prefer 'Month YYYY' everywhere.",
                     sorted(active), family="parser_safe"),
        AtsDimension("bullet_style", "Bullet style", bullet_style_score,
                     _STRUCTURE_WEIGHTS["bullet_style"],
                     f"{len(plain)} plain bullet(s), {len(decorative)} decorative bullet(s). "
                     "Use '-' or '•' so parsers split bullets.",
                     [ln[:80] for _, ln in (plain[:3] + decorative[:2])], family="parser_safe"),
        AtsDimension("text_integrity", "Text integrity", text_score, _STRUCTURE_WEIGHTS["text_integrity"],
                     "Alphanumeric ratio and document length indicate whether text extracts cleanly "
                     "(layout, images, tables).", [], family="parser_safe"),
        AtsDimension("contact", "Contact block", contact_score, _EXTRACTION_WEIGHTS["contact"],
                     f"{len(contact_evidence)} contact signals: {', '.join(contact_evidence) or 'none detected'}.",
                     contact_evidence, family="extraction"),
        AtsDimension("chronology", "Chronological experience", chrono_score, _EXTRACTION_WEIGHTS["chronology"],
                     f"{len(titles)} role title(s), {len(date_ranges)} date range(s).", titles[:4],
                     family="extraction"),
        AtsDimension("education", "Education", edu_score, _EXTRACTION_WEIGHTS["education"],
                     f"{', '.join(edu_evidence) or 'no degree or institution detected'}.", edu_evidence,
                     family="extraction"),
        AtsDimension("skills", "Skills section", skills_score, _EXTRACTION_WEIGHTS["skills"],
                     f"{len(bare_tokens)} bare skill tokens in a dedicated section; "
                     f"{len(skill_terms)} recognized technologies across {len(categories)} categories.",
                     skill_terms[:8], family="extraction"),
        AtsDimension("achievements", "Scannable bullets", exp_score, _EXTRACTION_WEIGHTS["achievements"],
                     f"{len(bullets)} bullets, {action_hits} action verbs, {impact_hits} quantified outcomes.",
                     bullets[:5], family="extraction"),
    ]
    weight_sum = sum(d.weight for d in dims)
    score = sum(d.score * d.weight for d in dims) / weight_sum
    scorable = bool(text and scores_nonzero(dims))
    if not scorable:
        score = 0.0

    counts = Counter(
        {"gap_lines": len(gap_lines), "creative": len(creative), "decorative": len(decorative)}
    )
    recs = _recommendations(
        text, spans, fields, sections, sec_present, titles, date_ranges, degrees,
        [ln for _, ln in plain], skill_terms, contact_evidence, name,
        placement_signals=placement_signals, head_start=head_start, head_end=head_end,
        gap_lines=gap_lines, creative=creative, decorative=decorative,
        formats=formats, chronological=(len(date_ranges) >= 1),
        _counts=counts,
    )
    return AtsResult(score=score, grade=_grade(score), dimensions=dims, recommendations=recs)


def scores_nonzero(dims: list[AtsDimension]) -> bool:
    return any(d.score > 0 for d in dims)


def _recommendations(
    text: str,
    spans: list[tuple[int, str]],
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
    placement_signals: list[str],
    head_start: int,
    head_end: int,
    gap_lines: list[tuple[int, str]],
    creative: list[tuple[int, str]],
    decorative: list[tuple[int, str]],
    formats: dict[str, list[tuple[int, int]]],
    chronological: bool,
    _counts: Counter,
) -> list[AtsRecommendation]:
    recs: list[AtsRecommendation] = []

    def add(sev: str, code: str, title: str, detail: str, action: str,
            start: int = -1, end: int = -1, line: int = -1) -> None:
        if start >= 0 and line < 0:
            line = _line_of(spans, start)
        recs.append(AtsRecommendation(sev, code, title, detail, action, start, end, line))

    if not text or len(text) < 200:
        add("high", "text_extract", "Text extraction looks weak",
            "Very little text was read from the document.",
            "Ensure the resume is a text-based PDF (not an image scan). Avoid tables, text boxes, and header/footer-only layouts.")
    if gap_lines:
        s, ln = gap_lines[0]
        add("high", "layout_columns", "Use a single-column layout",
            f"{_counts['gap_lines']} line(s) show wide interior gaps, a sign of multi-column text that scrambles on parse.",
            "Switch to a single-column layout with no text boxes or sidebars.",
            start=s, end=s + len(ln))
    if "email" not in contact:
        add("high", "no_email", "Add a plain-text email",
            "ATS parsers match candidates by email; none was found.",
            "Put a single email address in the contact line.")
    if "phone" not in contact:
        add("high", "no_phone", "Add a phone number",
            "No phone number was detected.",
            "Add a phone number in a standard format, e.g. (555) 123-4567.")
    if len(placement_signals) < 2:
        missing = [s for s in ("name", "email", "phone") if s not in placement_signals]
        add("medium", "contact_placement", "Move contact details to the top",
            f"Only {len(placement_signals)} contact signal(s) in the first {_CONTACT_LINES} body lines.",
            f"Put your {', '.join(missing)} in the top block of the first page.",
            start=head_start, end=head_end)
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
    if creative:
        s, ln = creative[0]
        shown = ", ".join(f"'{ln_}'" for _, ln_ in creative[:3])
        add("medium", "creative_headings", "Rename creative headings",
            f"{len(creative)} heading(s) don't match standard labels: {shown}.",
            "Rename them to standard labels like 'Work Experience', 'Education', 'Skills'.",
            start=s, end=s + len(ln))
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
    active = set(formats)
    if len(active) > 1:
        s, e = formats[sorted(active)[-1]][0]
        add("medium", "mixed_dates", "Use one date format",
            f"Multiple date formats detected: {', '.join(sorted(active))}.",
            "Rewrite every date as 'Month YYYY' (e.g. 'June 2022 – March 2024').",
            start=s, end=e)
    elif active and active != {"month_year"}:
        only = next(iter(active))
        s, e = formats[only][0]
        add("low", "date_format", "Prefer 'Month YYYY' dates",
            f"Dates use '{only}' instead of 'Month YYYY'.",
            "Rewrite dates as 'Month YYYY' so parsers read months and years.",
            start=s, end=e)
    if decorative:
        s, ln = decorative[0]
        add("medium", "decorative_bullets", "Replace decorative bullets",
            f"{len(decorative)} bullet(s) use arrows, checkmarks, or emoji that parsers drop.",
            "Use plain '-' or '•' bullets.",
            start=s, end=s + len(ln))
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
    return recs[:12]
