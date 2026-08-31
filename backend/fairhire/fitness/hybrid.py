"""Hybrid matching: LLM-extracted requirements -> deterministic matches.

The DeepSeek layer produces structured requirements (skill / degree / years /
soft / ability) plus resume evidence, and *also* judges requirements that the
lexical tiers cannot resolve (supersets, synonyms, novel skills — e.g. a resume
with "TypeScript" satisfies a "JavaScript" requirement). This module turns each
requirement into a match with an anchored resume span.

Determinism is preserved where it matters: scoring (see score.py) is a fixed
rule over the resulting matched/missing sets. The LLM may only UPGRADE a missing
requirement to matched (with evidence); it never downgrades a lexical match and
never produces a score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from fairhire.fitness import llm_extract as _llm
from fairhire.fitness.llm_extract import Requirement, ResumeEvidence, SemanticJudgment
from fairhire.fitness.matcher import (
    EXACT_SCORE,
    CONTAINS_SCORE,
    FAMILY_SCORE,
    INFERRED_SCORE,
    Link,
    _best_resume_occurrence,
    _contains_match,
    _family_match,
    _sentence_text,
    _token_spans,
)
from fairhire.fitness.ner import (
    ParsedDoc,
    _sentence_for,
    _all_tokens,
    find_occurrences,
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "the", "to", "with", "you", "your", "our",
    "their", "that", "this", "such", "strong", "ability", "skills", "skill",
    "experience", "including", "using", "etc", "able", "will", "can",
    "while", "when", "where", "which", "who", "how", "then", "than", "there",
    "these", "those", "also", "via", "both", "any", "all", "not", "very",
    "more", "most", "due", "among", "within", "between", "through", "during",
    "after", "before", "because", "since", "though", "although", "however",
    "therefore", "thus", "etc", "well", "within", "over", "under", "into",
}


@dataclass
class RequirementMatchRow:
    term: str
    kind: str
    required: bool
    matched: bool = False
    quality: str | None = None
    score: float = 0.0
    resume_term: str | None = None
    suggested: bool | None = None
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "kind": self.kind,
            "required": self.required,
            "matched": self.matched,
            "quality": self.quality,
            "score": round(self.score, 2) if self.matched else None,
            "resume_term": self.resume_term,
            "suggested": self.suggested,
            "hint": self.hint,
        }


@dataclass
class ConfirmItem:
    term: str
    kind: str
    required: bool
    suggested: bool | None
    hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "kind": self.kind,
            "required": self.required,
            "suggested": self.suggested,
            "hint": self.hint,
        }


@dataclass
class HybridResult:
    links: list[Link] = field(default_factory=list)
    rows: list[RequirementMatchRow] = field(default_factory=list)
    confirm_items: list[ConfirmItem] = field(default_factory=list)
    matched_required: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)

    @property
    def matched_optional(self) -> list[str]:
        return [
            r.term for r in self.rows if not r.required and r.matched
        ]


def _sig_tokens(text: str) -> list[str]:
    return [t for t in _all_tokens(text) if t not in STOPWORDS]


def _locate_in_jd(jd: ParsedDoc, phrase: str) -> tuple[int, int, int]:
    """Best-effort (sentence_index, start, end) for an LLM-extracted phrase."""
    phrase = phrase.strip()
    low = phrase.lower()
    idx = jd.text.lower().find(low)
    if idx >= 0:
        sent = _sentence_for(jd.sentences, idx)
        return sent, idx, idx + len(phrase)

    # Fallback: sentence with the highest significant-token overlap; anchor to
    # its first matched token.
    sig = _sig_tokens(phrase)
    best = (0, 0, 0, 0)  # (sent_idx, score, start, end)
    for s in jd.sentences:
        spans = _token_spans(s.text.lower())
        matches = [tok for tok in sig if any(tok == w for w, _, _ in spans)]
        if len(matches) > best[1]:
            w, st, en = next(
                (sp for sp in spans if sp[0] == matches[0]),
                (None, s.start, s.start + 1),
            )
            best = (s.index, len(matches), s.start + st, s.start + en)
    return best[0], best[2], best[3]


def _resume_sentence_with(resume: ParsedDoc, token: str) -> int:
    token = token.lower()
    for s in resume.sentences:
        if any(w.lower() == token for w, _, _ in _token_spans(s.text)):
            return s.index
    return -1


def _anchor_resume_sentence(resume: ParsedDoc, sent_idx: int, token: str | None) -> tuple[int, int]:
    if sent_idx < 0 or sent_idx >= len(resume.sentences):
        return 0, 1
    s = resume.sentences[sent_idx]
    if token:
        token = token.lower()
        for w, st, en in _token_spans(s.text):
            if w.lower() == token:
                return s.start + st, s.start + en
    return s.start, min(s.start + 1, s.end)


# Curated trigger -> evidence patterns so soft/ability requirements can be
# confirmed deterministically against the resume text.
_SOFT_TRIGGER_PATTERNS: dict[frozenset[str], str] = {
    frozenset({"analytical", "analysis", "analytical", "evaluat", "metric", "evaluate"}):
        r"\b(analyz\w*|analysis|evaluat\w*|metric\w*|diagnos\w*|benchmark\w*|data[- ]driven|root cause|sensor fusion)\b",
    frozenset({"troubleshoot", "bugs", "bug", "debug", "problem", "problems", "resolve", "issues", "issue"}):
        r"\b(troubleshoot\w*|debug\w*|resolv\w*|fix\w*|root cause|solved|workaround|reproduc\w*)\b",
    frozenset({"organizational", "organization", "coordinat", "schedul", "prioritiz", "organize"}):
        r"\b(organiz\w*|coordinat\w*|prioritiz\w*|schedul\w*|project manag\w*|led|managed)\b",
    frozenset({"communication", "communicat", "present", "presentation", "written", "documentation", "mentor", "mentoring", "teach", "teaching", "train"}):
        r"\b(communicat\w*|present\w*|document\w*|wrote|author\w*|explain\w*|mentor\w*|teach\w*|train\w*)\b",
    frozenset({"collaborate", "collaboration", "team", "teamwork", "cross-functional"}):
        r"\b(collaborat\w*|cross[- ]functional|paired|mentor\w*|coauthor\w*|co-authored)\b",
    frozenset({"leadership", "lead", "mentor", "coach", "direct"}):
        r"\b(led|lead\w*|mentor\w*|coach\w*|directed|owned)\b",
    frozenset({"detail", "detailed", "precis", "meticul", "rigor"}):
        r"\b(precis\w*|meticul\w*|detailed|rigor\w*)\b",
    frozenset({"self-motivated", "self-motivation", "proactive", "initiative", "autonom"}):
        r"\b(self[- ]direct\w*|initiat\w*|proactive|autonom\w*)\b",
}
_SOFT_TRIGGERS: list[tuple[frozenset[str], re.Pattern[str]]] = [
    (triggers, re.compile(pattern, re.I)) for triggers, pattern in _SOFT_TRIGGER_PATTERNS.items()
]

# Degree words that carry no matching signal (holder/degree boilerplate).
_DEGREE_TOPIC_STOP = {
    "bachelor", "bachelors", "b.s", "bs", "master", "masters", "m.s", "ms",
    "ph.d", "phd", "degree", "related", "field", "or", "and", "in", "a", "an",
    "of", "for", "with", "the", "equivalent", "other", "plus", "certification",
}


def _years_from_text(text: str) -> float | None:
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:years?|yrs)\b", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"at least\s+(\d{1,2})\s*(?:years?|yrs)?", text, re.I)
    if m:
        return float(m.group(1))
    return None


def _resume_total_years(resume: ParsedDoc, evidence: ResumeEvidence | None) -> float:
    if evidence and evidence.total_years and evidence.total_years > 0:
        return evidence.total_years
    ranges = resume.fields.get("date_ranges") or []
    years = []
    for rng in ranges:
        m = re.findall(r"(?:19|20)\d{2}", rng)
        if m:
            years.extend(int(y) for y in m)
    if not years:
        return 0.0
    span = max(years) - min(years)
    if span <= 0:
        return 0.0
    # Rough estimate: a contiguous-looking span counts fully.
    return float(min(span, 30))


def _match_skill(
    req: Requirement, jd: ParsedDoc, resume: ParsedDoc
) -> tuple[Link | None, str | None]:
    # 1. Ontology tier matching for any recognized term inside the requirement.
    occs = find_occurrences(req.text, [])
    for occ in occs:
        canonical = occ.canonical
        exact = _best_resume_occurrence(resume, canonical)
        if exact is not None:
            return _make_link(req, jd, resume, "exact", EXACT_SCORE, exact.variant,
                              exact.sentence_index, exact.start, exact.end), canonical
    for occ in occs:
        canonical = occ.canonical
        contains = _contains_match(resume, canonical)
        if contains is not None:
            _, si, ss, se, var = contains
            return _make_link(req, jd, resume, "contains", CONTAINS_SCORE, var, si, ss, se), canonical
        family = _family_match(resume, canonical)
        if family is not None:
            var, si, ss, se, mt = family
            return _make_link(req, jd, resume, "family", FAMILY_SCORE, mt, si, ss, se), canonical

    # 2. Token containment of the full requirement phrase in one resume sentence.
    contains = _contains_match(resume, req.text)
    if contains is not None:
        snippet, si, ss, se, var = contains
        return _make_link(req, jd, resume, "contains", CONTAINS_SCORE, var, si, ss, se), None
    return None, None


def _match_degree(
    req: Requirement, jd: ParsedDoc, resume: ParsedDoc, evidence: ResumeEvidence | None
) -> Link | None:
    req_topics = {t for t in _sig_tokens(req.text) if t not in _DEGREE_TOPIC_STOP}
    if not req_topics:
        return None

    degree_texts = []
    deg = resume.fields.get("degrees") or []
    if isinstance(deg, list):
        degree_texts.extend(deg)
    if evidence and evidence.degree:
        degree_texts.append(evidence.degree)
    if not degree_texts:
        return None

    resume_tokens = {t for d in degree_texts for t in _sig_tokens(d)}
    common = req_topics & resume_tokens
    if not common:
        return None

    tok = sorted(common)[0]
    sent_idx = _resume_sentence_with(resume, tok)
    if sent_idx < 0:
        sent_idx = 0
    ss, se = _anchor_resume_sentence(resume, sent_idx, tok)
    return _make_link(req, jd, resume, "exact", EXACT_SCORE, tok, sent_idx, ss, se)


def _match_years(
    req: Requirement, jd: ParsedDoc, resume: ParsedDoc, evidence: ResumeEvidence | None
) -> Link | None:
    min_years = _years_from_text(req.text)
    if min_years is None:
        return None
    total = _resume_total_years(resume, evidence)
    if total < min_years:
        return None
    # Anchor to a date-range sentence if possible.
    sent_idx = -1
    for s in resume.sentences:
        if re.search(r"(?:19|20)\d{2}\s*[-–—to]\s*", s.text):
            sent_idx = s.index
            break
    if sent_idx < 0:
        sent_idx = 0
    ss, se = _anchor_resume_sentence(resume, sent_idx, None)
    return _make_link(req, jd, resume, "exact", EXACT_SCORE, f"{total:.0f} years", sent_idx, ss, se)


def _match_soft_or_ability(
    req: Requirement, jd: ParsedDoc, resume: ParsedDoc, evidence: ResumeEvidence | None
) -> Link | None:
    """Match a soft/ability requirement only on strong, curated evidence.

    We deliberately avoid loose token/stem overlap (which produced misleading
    "word match" links like a mentorship requirement hitting "Full Stack
    Software Engineer"). A soft or ability requirement is only auto-confirmed
    when a curated trigger's evidence pattern appears in the resume. Anything
    else is left unresolved and surfaced to the user as a question.
    """
    req_sig = set(_sig_tokens(req.text))
    for triggers, pattern in _SOFT_TRIGGERS:
        if not (triggers & req_sig):
            continue
        for s in resume.sentences:
            m = pattern.search(s.text)
            if m:
                ss, se = s.start + m.start(), s.start + m.end()
                return _make_link(req, jd, resume, "contextual", CONTAINS_SCORE,
                                  m.group(0), s.index, ss, se)
    return None


def _make_link(
    req: Requirement,
    jd: ParsedDoc,
    resume: ParsedDoc,
    quality: str,
    score: float,
    resume_term: str,
    resume_sentence_index: int,
    resume_start: int,
    resume_end: int,
) -> Link:
    jd_sent_idx, jd_start, jd_end = _locate_in_jd(jd, req.text)
    return Link(
        canonical=req.text,
        jd_term=req.text,
        resume_term=resume_term,
        category=req.kind,
        required=req.required,
        quality=quality,
        score=score,
        jd_sentence_index=jd_sent_idx,
        jd_sentence_text=_sentence_text(jd, jd_sent_idx),
        jd_start=jd_start,
        jd_end=jd_end,
        resume_sentence_index=resume_sentence_index,
        resume_sentence_text=_sentence_text(resume, resume_sentence_index),
        resume_start=resume_start,
        resume_end=resume_end,
    )


def _anchor_evidence(
    resume: ParsedDoc, evidence: str
) -> tuple[int, int, int] | None:
    """Locate a quoted `evidence` substring in the resume.

    Returns (sentence_index, start, end) anchored to a real span, or None if the
    quote cannot be found (we never fabricate a link for unverifiable evidence).
    """
    evidence = re.sub(r"\s+", " ", (evidence or "")).strip()
    if len(evidence) < 2:
        return None
    idx = resume.text.lower().find(evidence.lower())
    if idx < 0:
        # Tolerate whitespace differences: match sentence-by-sentence.
        flat = re.sub(r"\s+", " ", evidence.lower())
        for s in resume.sentences:
            if not s.text:
                continue
            if flat in re.sub(r"\s+", " ", s.text.lower()):
                return s.index, s.start, min(s.start + 1, s.end)
        return None
    sent = _sentence_for(resume.sentences, idx)
    if sent < 0:
        return None
    s = resume.sentences[sent]
    start = max(s.start, idx)
    end = min(s.end, idx + len(evidence))
    if end <= start:
        start = s.start
        end = min(s.start + 1, s.end)
    return sent, start, end


def match_requirements(
    requirements: list[Requirement],
    jd: ParsedDoc,
    resume: ParsedDoc,
    resume_evidence: ResumeEvidence | None,
    config: Any | None = None,
    confirmations: dict[str, bool] | None = None,
    max_requirements: int = 24,
) -> HybridResult:
    result = HybridResult()
    seen: set[str] = set()
    for req in requirements[:max_requirements]:
        key = f"{req.required}:{req.kind}:{req.text.lower()}"
        if key in seen:
            continue
        seen.add(key)

        link: Link | None = None
        if req.kind == "degree":
            link = _match_degree(req, jd, resume, resume_evidence)
        elif req.kind == "years":
            link = _match_years(req, jd, resume, resume_evidence)
        elif req.kind == "skill":
            link, _ = _match_skill(req, jd, resume)
        else:
            link = _match_soft_or_ability(req, jd, resume, resume_evidence)

        row = RequirementMatchRow(
            term=req.text,
            kind=req.kind,
            required=req.required,
        )
        if link is not None:
            _mark_matched(result, row, link, req)
        else:
            (result.missing_required if req.required else result.missing_optional).append(req.text)
        result.rows.append(row)

    if config is not None:
        llm_enabled = bool(getattr(config, "llm_extraction_enabled", False))
    else:
        llm_enabled = False
    unresolved = [row for row in result.rows if not row.matched]
    if unresolved:
        confirmations = confirmations or {}

        # LLM suggestion + hint for every unresolved requirement. The LLM only
        # *advises* (does it look satisfied, and from which resume quote) — it
        # never decides the score. The user's explicit answer (confirmations)
        # is what flips a requirement, keeping the score deterministic.
        if llm_enabled:
            judged: list[SemanticJudgment] = _llm.judge_requirements(
                [r.term for r in unresolved], resume.text, config
            )
            by_req = {j.requirement.strip().lower(): j for j in judged}
        else:
            by_req = {}
        for row in unresolved:
            j = by_req.get(row.term.strip().lower())
            if j is not None:
                row.suggested = j.satisfied
                row.hint = (j.evidence or j.relation or "").strip()[:160]
            else:
                row.suggested = None

            answer = confirmations.get(row.term.strip().lower())
            if answer is True:
                _upgrade_to_matched(result, row, jd, resume, row.hint)
            # answer False / not answered -> stays missing (surfaced as a question).

    result.confirm_items = [
        ConfirmItem(row.term, row.kind, row.required, row.suggested, row.hint)
        for row in result.rows
        if not row.matched
    ]
    result.links.sort(
        key=lambda lnk: (0 if lnk.required else 1, -lnk.score, lnk.canonical.lower())
    )
    return result


def _mark_matched(result: HybridResult, row: RequirementMatchRow, link: Link, req: Requirement) -> None:
    row.matched = True
    row.quality = link.quality
    row.score = link.score
    row.resume_term = link.resume_term
    result.links.append(link)
    (result.matched_required if req.required else result.matched_optional).append(req.text)


def _upgrade_to_matched(
    result: HybridResult,
    row: RequirementMatchRow,
    jd: ParsedDoc,
    resume: ParsedDoc,
    hint: str,
) -> None:
    """Fold a user-confirmed requirement into the match set, deterministically.

    The user has confirmed the requirement; we anchor a connecting line to real
    resume text (the LLM's hint quote when available, else the requirement's own
    tokens). This is the only path that turns an uncertain requirement into a
    match, and it only runs on explicit user input.
    """
    row.matched = True
    row.quality = "inferred"
    row.score = INFERRED_SCORE

    linked = False
    if hint:
        anchored = _anchor_evidence(resume, hint)
        if anchored is not None:
            sent_idx, s_start, s_end = anchored
            req = Requirement(row.term, row.kind, row.required)
            link = _make_link(req, jd, resume, "inferred", INFERRED_SCORE,
                              hint[:80], sent_idx, s_start, s_end)
            result.links.append(link)
            row.resume_term = hint[:80]
            linked = True
    if not linked:
        # No verifiable quote — still count it (the user said so) but don't draw
        # a misleading connecting line.
        row.resume_term = row.term

    (result.matched_required if row.required else result.matched_optional).append(row.term)
    missing = result.missing_required if row.required else result.missing_optional
    if row.term in missing:
        missing.remove(row.term)


def rows_to_dicts(rows: list[RequirementMatchRow]) -> list[dict[str, Any]]:
    return [r.to_dict() for r in rows]
