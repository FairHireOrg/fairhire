"""NanoJev schema-fill: resume text in, JSON Resume schema out.

Uses the NanoJev decision contract (state + question + candidates ->
complete probability distribution) as a *ranking layer* over deterministic
candidate extraction:

* **State in**: the raw resume text (shared evaluation context).
* **Questions in**: one focused judgment per JSON Resume field — Choice
  (which candidate line is the name / title / company / school?), Boolean
  (is this section present?), Score (ordered completeness levels).
* **Distributions out**: every answer carries its full probability
  distribution, surfaced in the UI as per-field confidence.

The deterministic NER parser (``ner.parse_resume``) supplies exact fields
(email, phone, URLs, dates, degrees) and the candidate pool. Exact regex
matches are kept as-is; Jev only ranks among plausible candidates and
scores completeness — the same "AI never on the scoring path" pattern as
the rest of FairHire. When the inference service is unavailable the
module falls back to the deterministic parse alone.

Service contract: ``POST {NANOJEV_URL}/api/evaluate`` with
``{"states": [{"id", "state", "questions": {...}}]}``; limits are 32
states, 96 questions and 256 candidate paths per request, so large
resumes are split into sequential batches (the service keeps the model
loaded between requests).

Endpoint: ``POST /api/parse/jev`` (see ``api.py``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from fairhire.fitness.lexicon import section_aliases
from fairhire.fitness.ner import (
    DATE_RANGE_RE,
    DEGREE_RE,
    EMAIL_RE,
    PHONE_RE,
    URL_RE,
    parse_resume,
)
from fairhire.fitness.sections import _is_heading, _normalize_heading

__all__ = [
    "NANOJEV_URL",
    "JevField",
    "JevParseResult",
    "build_jev_payload",
    "jev_parse_text",
    "jsonresume_from_parsedoc",
]

NANOJEV_URL = "http://127.0.0.1:8765"

# Service limits (serve_decisions.py): 32 states, 96 questions, 256 paths.
_MAX_QUESTIONS = 96
_MAX_PATHS = 256
_MAX_CANDIDATES = 255

_BULLET_RE = re.compile(r"^\s*(?:[-*•·▪◦‣➔→⇒✓✔★☆►▸]|\d+[.)])\s*")
_CITY_STATE_RE = re.compile(
    r"\b(?:[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*,\s*)?"
    r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b"
)
_NAMEISH_RE = re.compile(r"^[A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+){0,4}$")

SECTION_KEYS = ("summary", "experience", "education", "skills", "projects", "certifications", "publications")


# ---------------------------------------------------------------------------
# Candidate extraction (deterministic pool; Jev ranks within it)
# ---------------------------------------------------------------------------


def _line_spans(text: str) -> list[tuple[int, str]]:
    spans: list[tuple[int, str]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        spans.append((offset, raw.rstrip("\r\n")))
        offset += len(raw)
    return spans


def _nonempty_lines(text: str) -> list[tuple[int, int, str]]:
    return [
        (i + 1, start, line)
        for i, (start, line) in enumerate(_line_spans(text))
        if line.strip()
    ]


def _contact_lines(lines: list[tuple[int, int, str]]) -> list[str]:
    out = []
    for _, _, line in lines:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
            out.append(line.strip())
    return out[:8]


def _name_candidates(lines: list[tuple[int, int, str]], limit: int = 24) -> list[str]:
    """Short capitalized punctuation-light lines, contact block first."""
    out: list[str] = []
    seen: set[str] = set()
    head = [l for _, _, l in lines[:8]]
    rest = [l for _, _, l in lines[8:]]
    for line in head + rest:
        s = line.strip()
        if not s or s.lower() in seen:
            continue
        if EMAIL_RE.search(s) or PHONE_RE.search(s) or URL_RE.search(s):
            continue
        if _is_heading(s):
            continue
        if len(s) > 42 or len(s.split()) > 5:
            continue
        letters = re.sub(r"[^A-Za-z ]", "", s)
        if not letters.strip():
            continue
        if _NAMEISH_RE.match(s) and not re.search(r"[,.|]$", s):
            out.append(s)
            seen.add(s.lower())
        if len(out) >= limit:
            break
    return out


def _title_candidates(lines: list[tuple[int, int, str]], limit: int = 24) -> list[str]:
    """Lines carrying role/title words or pipe-joined fragments."""
    out: list[str] = []
    seen: set[str] = set()
    for _, _, line in lines:
        s = line.strip()
        if not s or s.lower() in seen:
            continue
        if EMAIL_RE.search(s) or PHONE_RE.search(s) or URL_RE.search(s):
            continue
        if _BULLET_RE.match(s):
            continue
        if len(s) > 80 or len(s.split()) > 14:
            continue
        if _is_heading(s):
            continue
        if "|" in s or re.search(r"\b(engineer|developer|designer|manager|analyst|scientist|consultant|lead|specialist|coordinator|director|intern|architect|administrator)\b", s, re.I):
            out.append(s)
            seen.add(s.lower())
        if len(out) >= limit:
            break
    return out


def _location_candidates(lines: list[tuple[int, int, str]], limit: int = 16) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for _, _, line in lines:
        s = line.strip()
        if not s or s.lower() in seen:
            continue
        if EMAIL_RE.search(s) or PHONE_RE.search(s) or URL_RE.search(s):
            continue
        if _CITY_STATE_RE.search(s) and len(s) <= 60:
            out.append(s)
            seen.add(s.lower())
        if len(out) >= limit:
            break
    return out


def _url_candidates(lines: list[tuple[int, int, str]]) -> list[str]:
    out = []
    for _, _, line in lines:
        for m in URL_RE.finditer(line):
            url = m.group(0).strip()
            if url and url not in out:
                out.append(url)
    return out[:8]


def _summary_blocks(text: str, limit: int = 12) -> list[str]:
    """Sentence groups between headings, each a summary candidate."""
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _is_heading(s):
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        if EMAIL_RE.search(s) or PHONE_RE.search(s) or URL_RE.search(s):
            continue
        if DATE_RANGE_RE.search(s):
            continue
        if _BULLET_RE.match(s):
            continue
        current.append(s)
    if current:
        blocks.append(" ".join(current))
    # Prefer blocks of 2+ sentences in the upper half of the document.
    scored = list(enumerate(blocks))
    scored.sort(key=lambda t: (-(len(t[1].split(". ")) >= 2) * 1000, abs(len(blocks) // 2 - t[0])))
    return [re.sub(r"\s+", " ", b).strip() for _, b in scored[:limit] if len(b.split()) >= 4]


def _role_lines(lines: list[tuple[int, int, str]], limit: int = 8) -> list[tuple[int, int, str]]:
    """Lines carrying a date range — one per work entry."""
    out = []
    for ln, start, line in lines:
        if DATE_RANGE_RE.search(line):
            out.append((ln, start, line.strip()))
        if len(out) >= limit:
            break
    return out


def _fragments(line: str) -> list[str]:
    parts = [p.strip(" ·|-–—,") for p in re.split(r"[|–—]", line)]
    parts = [p for p in parts if p and len(p) <= 60]
    if len(parts) >= 2:
        return parts[:4]
    dm = DEGREE_RE.search(line)
    if dm:
        before = line[: dm.start()].strip(" ,|")
        after = line[dm.start():].strip(" ,|")
        return [before, after] if before else [after or line.strip()]
    return [line.strip()]


def _education_lines(lines: list[tuple[int, int, str]], limit: int = 4) -> list[tuple[int, int, str]]:
    out = []
    for ln, start, line in lines:
        s = line.strip()
        if DEGREE_RE.search(s) or re.search(r"\b(university|college|institute|school)\b", s, re.I):
            out.append((ln, start, s))
        if len(out) >= limit:
            break
    return out


def _skill_candidates(lines: list[tuple[int, int, str]], limit: int = 60) -> list[str]:
    """Comma/pipe separated tokens from skills-ish lines."""
    out: list[str] = []
    seen: set[str] = set()
    for _, _, line in lines:
        s = line.strip()
        if len(s.split()) < 4 and not ("," in s or "|" in s):
            continue
        if EMAIL_RE.search(s) or URL_RE.search(s):
            continue
        for token in re.split(r"[,;|\n]", s):
            token = _BULLET_RE.sub("", token).strip()
            token = re.sub(r"^(?:skills?|technical skills?|technologies)\s*:\s*", "", token, flags=re.I)
            if 2 <= len(token) <= 40 and token.lower() not in seen:
                seen.add(token.lower())
                out.append(token)
        if len(out) >= limit:
            break
    return out[:limit]


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------


@dataclass
class JevQuestion:
    qid: str
    type: str  # "boolean" | "choice" | "score"
    instructions: str
    criteria: dict[str, str] | list[str]

    def to_dict(self) -> dict[str, Any]:
        q: dict[str, Any] = {"type": self.type, "instructions": self.instructions}
        if self.type == "boolean":
            q["criteria"] = self.criteria
        elif self.type == "choice":
            q["criteria"] = self.criteria
        else:
            q["criteria"] = self.criteria
        return q

    @property
    def path_count(self) -> int:
        if self.type == "boolean":
            return len(self.criteria) if isinstance(self.criteria, dict) else 2
        if isinstance(self.criteria, list):
            return len(self.criteria)
        return len(self.criteria)


@dataclass
class JevBatch:
    state_id: str
    state: str
    questions: dict[str, JevQuestion]

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.state_id,
            "state": self.state,
            "questions": {qid: q.to_dict() for qid, q in self.questions.items()},
        }


@dataclass
class JevField:
    """One JSON Resume field with its winning value and full distribution."""

    path: str  # e.g. "basics.name" or "work.0.position"
    value: Any
    confidence: float
    distribution: dict[str, float] = field(default_factory=dict)
    candidates: list[str] = field(default_factory=list)
    question_type: str = "choice"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "distribution": {k: round(v, 4) for k, v in self.distribution.items()},
            "candidates": list(self.candidates)[:24],
            "question_type": self.question_type,
        }


@dataclass
class JevParseResult:
    resume_json: dict[str, Any]
    fields: dict[str, JevField]
    engine: str
    parse_ms: float
    fallback: bool
    service_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resume": self.resume_json,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "engine": self.engine,
            "parse_ms": round(self.parse_ms, 2),
            "fallback": self.fallback,
            "service_info": self.service_info,
        }


def build_jev_payload(text: str) -> list[JevBatch]:
    """Build the question batches for one resume (state = full text).

    Questions are chunked so each batch stays within the service limits
    (96 questions, 256 candidate paths). Candidate pools are capped so a
    typical resume fits in one batch; long resumes split into two.
    """
    lines = _nonempty_lines(text)
    contact = _contact_lines(lines)
    name_cands = _name_candidates(lines)
    title_cands = _title_candidates(lines)
    loc_cands = _location_candidates(lines)
    url_cands = _url_candidates(lines)
    summary_cands = _summary_blocks(text)
    roles = _role_lines(lines)
    edu_lines = _education_lines(lines)
    skill_cands = _skill_candidates(lines)

    questions: dict[str, JevQuestion] = {}

    def add(qid: str, q: JevQuestion) -> None:
        questions[qid] = q

    # --- basics -----------------------------------------------------------
    # Email/phone/URL are exact regex matches — deterministic already, so no
    # Choice question is asked for them (the service needs 2+ candidates).
    NONE_OPTION = "∅ none of these lines"

    def choice_cands(cands: list[str]) -> dict[str, str]:
        out = {f"c{i}": c for i, c in enumerate(cands[:_MAX_CANDIDATES])}
        if len(out) == 1:
            out["c999"] = NONE_OPTION
        return out

    if name_cands:
        add("basics.name", JevQuestion(
            "basics.name", "choice",
            "Which line is the candidate's full name?",
            choice_cands(name_cands),
        ))
    if title_cands:
        add("basics.label", JevQuestion(
            "basics.label", "choice",
            "Which line is the candidate's professional title or headline?",
            choice_cands(title_cands),
        ))
    if loc_cands:
        add("basics.location", JevQuestion(
            "basics.location", "choice",
            "Which line is the candidate's location (city, region, or address)?",
            choice_cands(loc_cands),
        ))

    # --- section presence (boolean) ---------------------------------------
    for key in SECTION_KEYS:
        label = key.capitalize()
        add(f"has_{key}", JevQuestion(
            f"has_{key}", "boolean",
            f"Does the resume contain a {label} section with real content?",
            {"true": f"a {label} section is present", "false": f"no {label} section is present"},
        ))

    # --- summary ----------------------------------------------------------
    if summary_cands:
        add("basics.summary", JevQuestion(
            "basics.summary", "choice",
            "Which passage is the professional summary (a short biography, not a job entry or skill list)?",
            choice_cands(summary_cands),
        ))

    # --- work entries -----------------------------------------------------
    for idx, (_, _, line) in enumerate(roles):
        frags = _fragments(line)
        add(f"work.{idx}.header", JevQuestion(
            f"work.{idx}.header", "choice",
            "Which fragment of this line is the job title (the role name)?",
            choice_cands(frags),
        ))
        if len(frags) >= 2:
            add(f"work.{idx}.company", JevQuestion(
                f"work.{idx}.company", "choice",
                "Which fragment of this line is the company or organization name?",
                choice_cands(frags),
            ))

    # --- education --------------------------------------------------------
    for idx, (_, _, line) in enumerate(edu_lines):
        frags = _fragments(line)
        add(f"education.{idx}.line", JevQuestion(
            f"education.{idx}.line", "choice",
            "Which fragment of this line is the degree or field of study?",
            choice_cands(frags),
        ))

    # --- skills -----------------------------------------------------------
    if skill_cands:
        add("skills", JevQuestion(
            "skills", "choice",
            "Which of these tokens are the candidate's strongest technical skills? Pick the most central one.",
            choice_cands(skill_cands),
        ))

    # --- completeness scores ----------------------------------------------
    add("score.contact", JevQuestion(
        "score.contact", "score",
        "How complete is the contact block (name, email, phone, location, links)?",
        ["missing", "partial", "complete"],
    ))
    add("score.sections", JevQuestion(
        "score.sections", "score",
        "How well does the resume cover the standard sections (summary, experience, education, skills)?",
        ["none", "minimal", "partial", "good", "complete"],
    ))
    add("score.scannability", JevQuestion(
        "score.scannability", "score",
        "How scannable is this resume for an automated parser (headings, dates, bullets)?",
        ["unscannable", "weak", "ok", "strong"],
    ))

    # --- chunk into service-limit batches --------------------------------
    batches: list[JevBatch] = []
    current: dict[str, JevQuestion] = {}
    paths = 0
    for qid, q in questions.items():
        if current and (len(current) + 1 > _MAX_QUESTIONS or paths + q.path_count > _MAX_PATHS):
            batches.append(JevBatch(f"resume-{len(batches)}", text, current))
            current = {}
            paths = 0
        current[qid] = q
        paths += q.path_count
    if current:
        batches.append(JevBatch(f"resume-{len(batches)}", text, current))
    return batches


# ---------------------------------------------------------------------------
# Answer mapping: distributions -> JSON Resume
# ---------------------------------------------------------------------------


_NONE_OPTION = "∅ none of these lines"


def _choice_value(answer: dict[str, Any], candidates: list[str]) -> tuple[Any, float, dict[str, float]]:
    probs = answer.get("probabilities") or {}
    dist = {k: float(v) for k, v in probs.items() if isinstance(v, (int, float))}
    choice = answer.get("choice") or answer.get("value") or ""
    m = re.match(r"^c(\d+)$", str(choice))
    value: Any = None
    if m:
        idx = int(m.group(1))
        if idx == 999 and dist.get("c999", 0) > 0:
            value = None  # model rejected every candidate
        else:
            value = candidates[idx] if 0 <= idx < len(candidates) else None
    elif str(choice) in candidates:
        value = str(choice)
    if value == _NONE_OPTION:
        value = None
    confidence = max(dist.values()) if dist else 0.0
    return value, confidence, dist


def _split_location(line: str) -> dict[str, Any]:
    """Best-effort city/region split of a location line."""
    loc: dict[str, Any] = {}
    parts = [p.strip() for p in re.split(r"[,|]", line) if p.strip()]
    if not parts:
        return loc
    city = parts[0]
    region = ""
    m = re.search(r"\b([A-Z]{2})\b", line)
    if m and len(parts[0]) <= 40:
        region = m.group(1)
        city = re.sub(r"\s*,?\s*\b[A-Z]{2}\b\s*$", "", parts[0]).strip()
    loc["city"] = city
    if region:
        loc["region"] = region
    if len(parts) > 1 and not region:
        loc["region"] = parts[1]
    return loc


def _iso_year(token: str) -> str:
    m = re.search(r"(?:19|20)\d{2}", token or "")
    return m.group(0) if m else ""


def _split_date_range(text: str) -> tuple[str, str]:
    m = DATE_RANGE_RE.search(text or "")
    if not m:
        return "", ""
    parts = re.split(r"\s*(?:[-–—]|to)\s*", m.group(0).strip(), maxsplit=1)
    start = _iso_year(parts[0]) if parts else ""
    end = _iso_year(parts[1]) if len(parts) > 1 else ""
    return start, end


def _bullets_after(lines: list[tuple[int, int, str]], start_line: int, stop_line: int) -> list[str]:
    out = []
    for ln, _, line in lines:
        if ln <= start_line or (stop_line and ln >= stop_line):
            continue
        if _BULLET_RE.match(line):
            out.append(_BULLET_RE.sub("", line).strip(" ·|-–—,"))
    return out


def jsonresume_from_parsedoc(text: str) -> dict[str, Any]:
    """Deterministic JSON Resume document (fallback + merge base)."""
    from fairhire.fitness.ats import _detect_name
    from fairhire.fitness.document import document_from_parsedoc

    doc = parse_resume(text)
    fields = doc.fields
    bodies = doc.section_bodies or {}

    name = _detect_name(text) or ""
    email = str(fields.get("email", "") or "")
    phone = str(fields.get("phone", "") or "")
    location = str(fields.get("location", "") or "")
    linkedin = str(fields.get("linkedin", "") or "")
    github = str(fields.get("github", "") or "")

    basics: dict[str, Any] = {}
    if name:
        basics["name"] = name
    if email:
        basics["email"] = email
    if phone:
        basics["phone"] = phone
    if location:
        basics["location"] = _split_location(location)
    if linkedin or github:
        basics["url"] = linkedin or github
    profiles = []
    if linkedin:
        profiles.append({"network": "LinkedIn", "url": linkedin})
    if github:
        profiles.append({"network": "GitHub", "url": github})
    if profiles:
        basics["profiles"] = profiles
    summary = bodies.get("summary", "").strip()
    if summary:
        basics["summary"] = re.sub(r"\s+", " ", summary)

    work: list[dict[str, Any]] = []
    for item in document_from_parsedoc(doc).experience:
        entry: dict[str, Any] = {}
        if item.title:
            entry["position"] = item.title
        if item.company:
            entry["name"] = item.company
        start, end = _split_date_range(f"{item.start} - {item.end}")
        if item.start:
            entry["startDate"] = start or item.start
        if item.end:
            entry["endDate"] = end or item.end
        if item.location:
            entry["location"] = item.location
        if item.bullets:
            entry["highlights"] = item.bullets
        if entry:
            work.append(entry)

    education: list[dict[str, Any]] = []
    for item in document_from_parsedoc(doc).education:
        entry = {}
        if item.degree:
            entry["studyType"] = item.degree
        if item.area:
            entry["area"] = item.area
        if item.school:
            entry["institution"] = item.school
        if item.year:
            entry["endDate"] = item.year
        if entry:
            education.append(entry)

    skills: list[dict[str, Any]] = []
    for s in document_from_parsedoc(doc).skills:
        skills.append({"name": s})

    out: dict[str, Any] = {"basics": basics}
    if work:
        out["work"] = work
    if education:
        out["education"] = education
    if skills:
        out["skills"] = skills
    if document_from_parsedoc(doc).projects:
        out["projects"] = [{"name": p} for p in document_from_parsedoc(doc).projects]
    if document_from_parsedoc(doc).certifications:
        out["certifications"] = [{"name": c} for c in document_from_parsedoc(doc).certifications]
    return out


# ---------------------------------------------------------------------------
# Service call + merge
# ---------------------------------------------------------------------------


def _post_batch(batch: JevBatch, timeout: float = 120.0) -> dict[str, Any]:
    import json as _json
    import urllib.request

    payload = {"states": [batch.to_payload()]}
    req = urllib.request.Request(
        f"{NANOJEV_URL}/api/evaluate",
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return _json.loads(resp.read().decode("utf-8"))


def _merge_answers(
    batches: list[JevBatch],
    service_response: dict[str, Any],
    text: str,
) -> dict[str, JevField]:
    """Map service answers onto candidate pools -> JevField per resume path."""
    lines = _nonempty_lines(text)
    name_cands = _name_candidates(lines)
    title_cands = _title_candidates(lines)
    loc_cands = _location_candidates(lines)
    url_cands = _url_candidates(lines)
    summary_cands = _summary_blocks(text)
    roles = _role_lines(lines)
    edu_lines = _education_lines(lines)
    skill_cands = _skill_candidates(lines)

    answers: dict[str, Any] = {}
    for state in service_response.get("states", []):
        answers.update(state.get("answers", {}))

    fields: dict[str, JevField] = {}

    def record(qid: str, path: str, cands: list[str], qtype: str = "choice") -> None:
        ans = answers.get(qid)
        if not ans:
            return
        if qtype == "choice":
            value, conf, dist = _choice_value(ans, cands)
        else:
            value = bool(ans.get("value"))
            conf = float(ans.get("p_true", 0.0))
            dist = {str(k): float(v) for k, v in (ans.get("probabilities") or {}).items()}
        fields[path] = JevField(path=path, value=value, confidence=conf, distribution=dist, candidates=cands, question_type=qtype)

    record("basics.name", "basics.name", name_cands)
    record("basics.label", "basics.label", title_cands)
    record("basics.location", "basics.location", loc_cands)
    record("basics.url", "basics.url", url_cands)
    record("basics.summary", "basics.summary", summary_cands)
    for idx in range(len(roles)):
        record(f"work.{idx}.header", f"work.{idx}.position", _fragments(roles[idx][2]))
        record(f"work.{idx}.company", f"work.{idx}.name", _fragments(roles[idx][2]))
    for idx in range(len(edu_lines)):
        record(f"education.{idx}.line", f"education.{idx}.studyType", _fragments(edu_lines[idx][2]))
    record("skills", "skills", skill_cands)
    for key in SECTION_KEYS:
        record(f"has_{key}", f"section.{key}", [], qtype="boolean")
    score_levels = {
        "score.contact": ["missing", "partial", "complete"],
        "score.sections": ["none", "minimal", "partial", "good", "complete"],
        "score.scannability": ["unscannable", "weak", "ok", "strong"],
    }
    for sid, levels in score_levels.items():
        ans = answers.get(sid)
        if ans:
            probs = {str(k): float(v) for k, v in (ans.get("probabilities") or {}).items()}
            level = int(ans.get("level", 0))
            label = levels[level] if 0 <= level < len(levels) else str(level)
            fields[sid] = JevField(
                path=sid,
                value={"label": label, "level": level, "score": float(ans.get("score", 0.0))},
                confidence=max(probs.values()) if probs else 0.0,
                distribution=probs,
                question_type="score",
            )
    return fields


def _apply_jev_overrides(resume: dict[str, Any], fields: dict[str, JevField]) -> None:
    """Apply high-confidence Jev choices onto the deterministic document.

    Jev never *removes* deterministic exact matches (email/phone/URL regex);
    it fills fields the deterministic parser left empty and re-ranks
    ambiguous ones (name, title, company, summary).
    """
    basics = resume.setdefault("basics", {})

    f = fields.get("basics.name")
    if f and f.value and f.confidence >= 0.35 and not basics.get("name"):
        basics["name"] = f.value

    f = fields.get("basics.label")
    if f and f.value and f.confidence >= 0.35 and not basics.get("label"):
        basics["label"] = f.value

    f = fields.get("basics.location")
    if f and f.value and f.confidence >= 0.35 and not basics.get("location"):
        basics["location"] = _split_location(f.value)

    f = fields.get("basics.url")
    if f and f.value and f.confidence >= 0.35 and not basics.get("url"):
        basics["url"] = f.value

    f = fields.get("basics.summary")
    if f and f.value and f.confidence >= 0.30 and not basics.get("summary"):
        basics["summary"] = re.sub(r"\s+", " ", str(f.value)).strip()

    work = resume.get("work") or []
    for idx, entry in enumerate(work):
        f = fields.get(f"work.{idx}.position")
        if f and f.value and f.confidence >= 0.35 and not entry.get("position"):
            entry["position"] = f.value
        f = fields.get(f"work.{idx}.name")
        if f and f.value and f.confidence >= 0.35 and not entry.get("name"):
            entry["name"] = f.value

    education = resume.get("education") or []
    for idx, entry in enumerate(education):
        f = fields.get(f"education.{idx}.studyType")
        if f and f.value and f.confidence >= 0.35 and not entry.get("studyType"):
            entry["studyType"] = f.value


def jev_parse_text(resume_text: str, service_url: str | None = None) -> JevParseResult:
    """Parse resume text into a JSON Resume document via NanoJev + rules.

    Deterministic-first: the rule parser always produces the base document;
    the Jev service ranks candidates and fills gaps when reachable.
    """
    import time

    if resume_text is None or not str(resume_text).strip():
        raise ValueError("Provide resume text to parse.")
    text = str(resume_text)
    if len(text) > 100000:
        raise ValueError("Resume text must be under 100,000 characters.")

    global NANOJEV_URL
    if service_url:
        NANOJEV_URL = service_url

    t0 = time.perf_counter()
    resume = jsonresume_from_parsedoc(text)
    fields: dict[str, JevField] = {}
    fallback = True
    service_info: dict[str, Any] = {"url": NANOJEV_URL}

    try:
        batches = build_jev_payload(text)
        service_info["batches"] = len(batches)
        service_info["questions"] = sum(len(b.questions) for b in batches)
        merged: dict[str, JevField] = {}
        for batch in batches:
            response = _post_batch(batch)
            merged.update(_merge_answers([batch], response, text))
        fields = merged
        _apply_jev_overrides(resume, fields)
        fallback = False
        service_info["engine"] = "nanojev-schema-fill"
    except Exception as exc:  # noqa: BLE001 - deterministic fallback path
        logging.warning("NanoJev schema-fill unavailable (%s); using deterministic parse", exc)
        service_info["error"] = str(exc)
        service_info["engine"] = "deterministic-fallback"

    parse_ms = (time.perf_counter() - t0) * 1000.0
    return JevParseResult(
        resume_json=resume,
        fields=fields,
        engine=service_info["engine"],
        parse_ms=parse_ms,
        fallback=fallback,
        service_info=service_info,
    )
