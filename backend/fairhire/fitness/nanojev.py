"""NanoJev-style instant resume parsing from raw text.

A nano replica of the Jev/NanoJev decision contract, adapted to resumes:

* **State in**: the raw resume text (shared evaluation context).
* **Questions in**: a fixed batch of independent field judgments — Boolean
  (is it present?), Choice (which section does this line belong to?), Score
  (ordered completeness levels).
* **Distributions out**: every question returns its *complete* probability
  distribution — never just a label — with zero output-token decoding.
* **One backbone forward**: a single deterministic scan (line spans,
  sentences, ontology hits, fields, section map) is built once per text;
  all questions are pure functions over that cached evidence. Questions
  share state but never consume each other's answers, so the whole batch
  evaluates in one pass (~single-digit ms on typical resumes).

No LLMs. No embeddings. Fully deterministic: identical input always yields
identical distributions.

Endpoint: ``POST /api/parse/instant`` (see ``api.py``).
Frontend: ``parseInstant`` in ``frontend/lib/api.ts``.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from fairhire.fitness.lexicon import section_aliases
from fairhire.fitness.ner import (
    DEGREE_RE,
    EMAIL_RE,
    PHONE_RE,
    URL_RE,
    ParsedDoc,
    parse_resume,
)
from fairhire.fitness.sections import _is_heading, _normalize_heading

__all__ = [
    "BOOLEAN_QUESTIONS",
    "CHOICE_OPTIONS",
    "SCORE_LEVELS",
    "parse_instant",
    "parse_batch",
    "answer_questions",
]

# ---------------------------------------------------------------------------
# Question catalogue (ids identify responses; ids never enter the evidence)
# ---------------------------------------------------------------------------

BOOLEAN_QUESTIONS: tuple[str, ...] = (
    "has_email",
    "has_phone",
    "has_location",
    "has_linkedin",
    "has_github",
    "has_name",
    "has_summary",
    "has_experience",
    "has_education",
    "has_skills",
    "has_projects",
    "has_certifications",
    "has_dates",
    "has_bullets",
    "has_degree",
)

CHOICE_OPTIONS: tuple[str, ...] = (
    "contact",
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "other",
)

SCORE_LEVELS: dict[str, tuple[str, ...]] = {
    "contact_completeness": ("missing", "partial", "complete"),
    "section_coverage": ("none", "minimal", "partial", "good", "complete"),
    "scannability": ("unscannable", "weak", "ok", "strong"),
}

_BULLET_RE = re.compile(r"^\s*(?:[-*\u2022\u00b7\u25aa\u25e6\u2023]|\d+[.)])\s*")
_DATE_HINT_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)?\s*(?:19|20)\d{2}\b|\bPresent\b|\bCurrent\b",
    re.I,
)
_INSTITUTION_RE = re.compile(r"\b(?:university|college|institute|institut|school)\b", re.I)


# ---------------------------------------------------------------------------
# Probability heads (shared, deterministic)
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(v - m) for v in logits]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


@dataclass
class BooleanAnswer:
    id: str
    value: bool
    p_true: float
    distribution: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "boolean",
            "value": self.value,
            "p_true": round(self.p_true, 4),
            "distribution": [round(p, 4) for p in self.distribution],
        }


@dataclass
class ChoiceAnswer:
    id: str
    chosen: str
    probabilities: dict[str, float]
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "choice",
            "chosen": self.chosen,
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "confidence": round(self.confidence, 4),
        }


@dataclass
class ScoreAnswer:
    id: str
    level: int
    label: str
    score: float
    probabilities: list[float]
    levels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "score",
            "level": self.level,
            "label": self.label,
            "score": round(self.score, 4),
            "probabilities": [round(p, 4) for p in self.probabilities],
            "levels": list(self.levels),
        }


# ---------------------------------------------------------------------------
# Backbone: one deterministic scan per text (the "single forward pass")
# ---------------------------------------------------------------------------


@dataclass
class _Backbone:
    text: str
    doc: ParsedDoc
    line_spans: list[tuple[int, str]]
    nonempty: list[tuple[int, int, str]]  # (line_no, start, text)
    section_of_line: dict[int, str]  # 1-based line_no -> section key or ""
    name: str | None

    @property
    def sections(self) -> dict[str, bool]:
        return self.doc.sections

    @property
    def fields(self) -> dict[str, Any]:
        return self.doc.fields


def _line_spans(text: str) -> list[tuple[int, str]]:
    spans: list[tuple[int, str]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        spans.append((offset, raw.rstrip("\r\n")))
        offset += len(raw)
    return spans


def _build_backbone(text: str) -> _Backbone:
    from fairhire.fitness.ats import _detect_name

    doc = parse_resume(text)
    spans = _line_spans(text)
    nonempty: list[tuple[int, int, str]] = [
        (i + 1, start, line) for i, (start, line) in enumerate(spans) if line.strip()
    ]

    # Section map: walk headings once; lines before the first heading with
    # contact signals belong to the contact block.
    aliases = section_aliases()
    section_of_line: dict[int, str] = {}
    current = ""
    for i, (_, line) in enumerate(spans):
        line_no = i + 1
        if _is_heading(line):
            norm = _normalize_heading(line.rstrip(":").strip())
            hit = next((k for k, group in aliases.items() if norm in group), None)
            if hit is not None:
                current = hit
                section_of_line[line_no] = hit
                continue
        section_of_line[line_no] = current

    return _Backbone(
        text=text,
        doc=doc,
        line_spans=spans,
        nonempty=nonempty,
        section_of_line=section_of_line,
        name=_detect_name(text),
    )


# ---------------------------------------------------------------------------
# Question heads: pure functions over backbone evidence (no cross-talk)
# ---------------------------------------------------------------------------


def _boolean_logit(qid: str, bb: _Backbone) -> float:
    """Logit margin for each Boolean question; sigmoid -> p_true."""
    f = bb.fields
    s = bb.sections
    t = bb.text
    if qid == "has_email":
        return 6.0 if f.get("email") else -6.0
    if qid == "has_phone":
        return 6.0 if f.get("phone") else -6.0
    if qid == "has_location":
        return 6.0 if f.get("location") else -6.0
    if qid == "has_linkedin":
        return 6.0 if f.get("linkedin") else -6.0
    if qid == "has_github":
        return 6.0 if f.get("github") else -6.0
    if qid == "has_name":
        return 4.0 if bb.name else -4.0
    if qid == "has_summary":
        return 4.0 if s.get("summary") else -4.0
    if qid == "has_experience":
        return 4.0 if s.get("experience") else -4.0
    if qid == "has_education":
        return 4.0 if s.get("education") else -4.0
    if qid == "has_skills":
        return 4.0 if s.get("skills") else -4.0
    if qid == "has_projects":
        return 4.0 if s.get("projects") else -4.0
    if qid == "has_certifications":
        return 4.0 if s.get("certifications") else -4.0
    if qid == "has_dates":
        ranges = f.get("date_ranges") or []
        return 4.0 if ranges else -4.0
    if qid == "has_bullets":
        n = sum(1 for _, line in bb.line_spans if line.strip() and _BULLET_RE.match(line))
        return 4.0 if n >= 1 else -4.0
    if qid == "has_degree":
        degrees = f.get("degrees") or []
        return 4.0 if degrees else -4.0
    raise ValueError(f"unknown boolean question: {qid}")


def _choice_logits(line: str, section: str) -> list[float]:
    """Per-line section logits over CHOICE_OPTIONS."""
    logits = [0.0] * len(CHOICE_OPTIONS)
    idx = {name: i for i, name in enumerate(CHOICE_OPTIONS)}
    section_key = section if section in idx else ""
    if section_key:
        logits[idx[section_key]] += 3.0
    else:
        logits[idx["other"]] += 1.0
    if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
        logits[idx["contact"]] += 2.5
    if _DATE_HINT_RE.search(line):
        logits[idx["experience"]] += 1.5
    if DEGREE_RE.search(line) or _INSTITUTION_RE.search(line):
        logits[idx["education"]] += 1.5
    if _BULLET_RE.match(line):
        logits[idx["experience"]] += 1.0
    if "," in line and len(re.findall(r"[A-Za-z][A-Za-z0-9.+#\-]{1,24}", line)) >= 4:
        logits[idx["skills"]] += 1.0
    return logits


def _score_logits(sid: str, bb: _Backbone) -> list[float]:
    f = bb.fields
    s = bb.sections
    if sid == "contact_completeness":
        slots = [bool(f.get("email")), bool(f.get("phone")), bool(f.get("location")),
                 bool(f.get("linkedin") or f.get("github")), bool(bb.name)]
        filled = sum(slots)
        if filled >= 4:
            return [0.2, 1.0, 3.0]
        if filled >= 2:
            return [0.2, 2.5, 1.0]
        return [2.5, 0.8, 0.1]
    if sid == "section_coverage":
        core = sum(1 for k in ("summary", "experience", "skills", "education") if s.get(k))
        bonus = sum(1 for k in ("projects", "publications", "certifications") if s.get(k))
        total = core + min(bonus, 1)
        table = {
            0: [3.0, 0.5, 0.1, 0.0, 0.0],
            1: [0.5, 2.5, 1.0, 0.2, 0.0],
            2: [0.1, 0.8, 2.5, 1.0, 0.2],
            3: [0.0, 0.2, 1.0, 2.5, 1.0],
        }
        return table.get(total, [0.0, 0.2, 0.8, 1.5, 3.0])
    if sid == "scannability":
        bullets = sum(1 for _, line in bb.line_spans if line.strip() and _BULLET_RE.match(line))
        dates = len(f.get("date_ranges") or [])
        if bullets >= 3 and dates >= 1:
            return [0.0, 0.3, 1.2, 3.0]
        if bullets >= 1 and dates >= 1:
            return [0.1, 0.8, 2.5, 1.0]
        if bullets >= 1 or dates >= 1:
            return [0.5, 2.2, 1.0, 0.2]
        return [2.5, 1.0, 0.2, 0.0]
    raise ValueError(f"unknown score question: {sid}")


def answer_questions(bb: _Backbone) -> tuple[list[BooleanAnswer], list[ChoiceAnswer], list[ScoreAnswer]]:
    """Evaluate the full independent question batch over cached evidence."""
    booleans = [
        BooleanAnswer(id=qid, value=False, p_true=0.0)
        for qid in BOOLEAN_QUESTIONS
    ]
    for ans in booleans:
        p = _sigmoid(_boolean_logit(ans.id, bb))
        ans.p_true = p
        ans.value = p >= 0.5
        ans.distribution = [1.0 - p, p]

    choices: list[ChoiceAnswer] = []
    for line_no, start, line in bb.nonempty:
        section = bb.section_of_line.get(line_no, "")
        probs = _softmax(_choice_logits(line, section))
        mapping = {name: probs[i] for i, name in enumerate(CHOICE_OPTIONS)}
        best = max(range(len(probs)), key=lambda i: probs[i])
        choices.append(ChoiceAnswer(
            id=f"line:{line_no}",
            chosen=CHOICE_OPTIONS[best],
            probabilities=mapping,
            confidence=probs[best],
        ))

    scores: list[ScoreAnswer] = []
    for sid, levels in SCORE_LEVELS.items():
        probs = _softmax(_score_logits(sid, bb))
        level = max(range(len(probs)), key=lambda i: probs[i])
        expectation = sum(i * p for i, p in enumerate(probs))
        scores.append(ScoreAnswer(
            id=sid, level=level, label=levels[level], score=expectation,
            probabilities=probs, levels=list(levels),
        ))
    return booleans, choices, scores


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def parse_instant(resume_text: str) -> dict[str, Any]:
    """Parse raw resume text in a single deterministic pass.

    Returns complete Boolean/Choice/Score distributions plus the structured
    fields, section map, skill spans and editable document — everything the
    UI needs for instant as-you-type feedback.
    """
    if resume_text is None or not str(resume_text).strip():
        raise ValueError("Provide resume_text to parse.")
    text = str(resume_text)
    if len(text) > 100000:
        raise ValueError("Resume text must be under 100,000 characters.")
    t0 = time.perf_counter()

    bb = _build_backbone(text)
    booleans, choices, scores = answer_questions(bb)

    from fairhire.fitness.document import document_from_parsedoc

    doc = document_from_parsedoc(bb.doc)
    try:
        from fairhire.fitness.ats import evaluate_ats

        ats = evaluate_ats(bb.doc)
        ats_preview = {"score": round(ats.score, 1), "grade": ats.grade}
    except Exception:
        ats_preview = {"score": 0.0, "grade": "Likely missed"}

    skills = [
        {
            "canonical": o.canonical,
            "variant": o.variant,
            "category": o.category,
            "start": o.start,
            "end": o.end,
            "sentence": o.sentence_index,
        }
        for o in bb.doc.occurrences
    ]

    parse_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "engine": "nanojev-instant",
        "parse_ms": round(parse_ms, 2),
        "text_len": len(text),
        "booleans": [a.to_dict() for a in booleans],
        "line_choices": [
            {
                **c.to_dict(),
                "line": int(c.id.split(":")[1]),
                "start": next(s for n, s, _ in bb.nonempty if f"line:{n}" == c.id),
                "text": next(t for n, _, t in bb.nonempty if f"line:{n}" == c.id)[:200],
            }
            for c in choices
        ],
        "scores": [s.to_dict() for s in scores],
        "fields": bb.fields,
        "sections_found": dict(bb.sections),
        "skills": skills,
        "document": doc.to_dict(),
        "ats_preview": ats_preview,
    }


def parse_batch(texts: list[str]) -> list[dict[str, Any]]:
    """Batch independent states — one backbone pass each, no cross-talk."""
    if not isinstance(texts, list) or not texts:
        raise ValueError("Provide a non-empty list of resume texts.")
    if len(texts) > 25:
        raise ValueError("Batch is limited to 25 texts per request.")
    return [parse_instant(t) for t in texts]
