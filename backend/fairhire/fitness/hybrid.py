"""LLM-extracted JD requirements verified against literal resume evidence."""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass, field
from typing import Any

from fairhire.fitness.llm_extract import Requirement
from fairhire.fitness.matcher import (
    CONTEXTUAL_SCORE,
    EXACT_SCORE,
    FAMILY_SCORE,
    Link,
    _best_resume_occurrence,
    _contains_match,
    _family_match,
    _sentence_text,
    _token_spans,
    link_is_valid,
)
from fairhire.fitness.ner import ParsedDoc, _all_tokens, _sentence_for, find_occurrences

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "the", "to", "with", "you", "your", "our",
    "that", "this", "strong", "ability", "skills", "skill", "experience", "using",
    "required", "preferred", "including", "able", "will", "can",
}
WEAK_OBJECTS = {
    "software", "work", "team", "project", "projects", "system", "systems", "application",
    "applications", "support", "development", "design", "build", "new",
}
ACTION_STEMS = {"develop", "test", "maintain", "debug", "design", "build", "lead", "manage", "analyz", "implement", "ship", "collaborat"}

_SOFT_TRIGGER_PATTERNS: list[tuple[frozenset[str], re.Pattern[str]]] = [
    (frozenset({"analytical", "analysis", "problem", "resolve"}), re.compile(r"\b(analyz\w*|analysis|diagnos\w*|root cause|resolv\w*)\b", re.I)),
    (frozenset({"troubleshoot", "debug", "bugs", "issues"}), re.compile(r"\b(troubleshoot\w*|debug\w*|fix\w*|reproduc\w*)\b", re.I)),
    (frozenset({"communication", "present", "written", "documentation"}), re.compile(r"\b(communicat\w*|present\w*|document\w*|authored|wrote)\b", re.I)),
    (frozenset({"collaborate", "collaboration", "teamwork", "cross-functional"}), re.compile(r"\b(collaborat\w*|cross[- ]functional|paired)\b", re.I)),
    (frozenset({"leadership", "lead", "mentor", "coach"}), re.compile(r"\b(led|lead\w*|mentor\w*|coach\w*|directed|owned)\b", re.I)),
    (frozenset({"organizational", "coordinate", "prioritize"}), re.compile(r"\b(organiz\w*|coordinat\w*|prioritiz\w*|schedul\w*)\b", re.I)),
]

_DEGREE_STOP = {
    "bachelor", "bachelors", "b.s", "bs", "master", "masters", "m.s", "ms", "ph.d",
    "phd", "degree", "related", "field", "equivalent", "of", "for", "with", "the",
}


@dataclass
class RequirementMatchRow:
    term: str
    kind: str
    required: bool
    source_text: str = ""
    jd_start: int = -1
    jd_end: int = -1
    matched: bool = False
    quality: str | None = None
    score: float = 0.0
    resume_term: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": hashlib.sha256(f"{self.kind}|{self.term.casefold()}|{self.jd_start}|{self.jd_end}".encode()).hexdigest()[:16],
            "term": self.term,
            "kind": self.kind,
            "required": self.required,
            "source_text": self.source_text,
            "jd_start": self.jd_start,
            "jd_end": self.jd_end,
            "matched": self.matched,
            "quality": self.quality,
            "score": round(self.score, 2) if self.matched else None,
            "resume_term": self.resume_term,
            "reason": ("Literal term or curated alias found." if self.quality == "exact" else
                       "An explicit technology relationship supports this match." if self.quality == "family" else
                       "A contextual rule found supporting language in one sentence." if self.matched else
                       "No supported literal evidence found. This does not establish that you lack this qualification."),
        }


@dataclass
class HybridResult:
    links: list[Link] = field(default_factory=list)
    rows: list[RequirementMatchRow] = field(default_factory=list)
    matched_required: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)

    @property
    def matched_optional(self) -> list[str]:
        return [row.term for row in self.rows if not row.required and row.matched]


def _sig_tokens(text: str) -> list[str]:
    return [token for token in _all_tokens(text) if token not in STOPWORDS]


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _jd_anchor(requirement: Requirement, jd: ParsedDoc) -> tuple[int, int, int] | None:
    start, end = requirement.jd_start, requirement.jd_end
    if start < 0 or end <= start or jd.text[start:end] != requirement.source_text:
        return None
    sentence_index = _sentence_for(jd.sentences, start)
    if sentence_index < 0:
        return None
    sentence = jd.sentences[sentence_index]
    if end > sentence.end:
        return None
    return sentence_index, start, end


def _make_link(
    requirement: Requirement,
    jd: ParsedDoc,
    resume: ParsedDoc,
    quality: str,
    score: float,
    resume_term: str,
    sentence_index: int,
    start: int,
    end: int,
) -> Link | None:
    anchor = _jd_anchor(requirement, jd)
    if anchor is None:
        return None
    evidence_sentence = _sentence_text(resume, sentence_index)
    if re.search(r"\b(?:no|not|never|without|lack\w*|learning|beginner|exposure only)\b", evidence_sentence, re.I):
        return None
    jd_sentence_index, jd_start, jd_end = anchor
    link = Link(
        canonical=requirement.text,
        jd_term=jd.text[jd_start:jd_end],
        resume_term=resume.text[start:end],
        category=requirement.kind,
        required=requirement.required,
        quality=quality,
        score=score,
        jd_sentence_index=jd_sentence_index,
        jd_sentence_text=_sentence_text(jd, jd_sentence_index),
        jd_start=jd_start,
        jd_end=jd_end,
        resume_sentence_index=sentence_index,
        resume_sentence_text=_sentence_text(resume, sentence_index),
        resume_start=start,
        resume_end=end,
    )
    return link if link_is_valid(link, jd, resume) else None


def _match_skill(requirement: Requirement, jd: ParsedDoc, resume: ParsedDoc) -> Link | None:
    occurrences = find_occurrences(requirement.text, [])
    if len(occurrences) != 1 or occurrences[0].canonical.casefold() != requirement.text.casefold():
        return None
    for occurrence in occurrences:
        exact = _best_resume_occurrence(resume, occurrence.canonical)
        if exact:
            return _make_link(requirement, jd, resume, "exact", EXACT_SCORE, exact.text, exact.sentence_index, exact.start, exact.end)
    for occurrence in occurrences:
        contextual = _contains_match(resume, occurrence.canonical)
        if contextual:
            _, si, start, end, text = contextual
            return _make_link(requirement, jd, resume, "contextual", CONTEXTUAL_SCORE, text, si, start, end)
        family = _family_match(resume, occurrence.canonical)
        if family:
            _, si, start, end, text = family
            return _make_link(requirement, jd, resume, "family", FAMILY_SCORE, text, si, start, end)
    contextual = _contains_match(resume, requirement.text)
    if contextual:
        _, si, start, end, text = contextual
        return _make_link(requirement, jd, resume, "contextual", CONTEXTUAL_SCORE, text, si, start, end)
    return None


def _match_degree(requirement: Requirement, jd: ParsedDoc, resume: ParsedDoc) -> Link | None:
    levels = [r"\b(?:bachelor(?:'s)?|b\.?s\.?|b\.?a\.?|bsc)\b", r"\b(?:master(?:'s)?|m\.?s\.?|msc|mba)\b", r"\b(?:ph\.?d|doctorate)\b"]
    level = next((p for p in levels if re.search(p, requirement.text, re.I)), None)
    if not level:
        return None
    subject = re.search(r"\b(?:in|of)\s+(.+?)(?:,|\bor\b|\(|$)", requirement.text, re.I)
    topic = re.sub(r"^(?:science|arts)\s+in\s+", "", subject.group(1), flags=re.I).strip() if subject else ""
    for sentence in resume.sentences:
        if not re.search(level, sentence.text, re.I):
            continue
        if topic and not re.search(r"(?<!\w)" + re.escape(topic) + r"(?!\w)", sentence.text, re.I):
            continue
        return _make_link(requirement, jd, resume, "contextual", CONTEXTUAL_SCORE, sentence.text, sentence.index, sentence.start, sentence.end)
    return None


def _match_years(requirement: Requirement, jd: ParsedDoc, resume: ParsedDoc) -> Link | None:
    required_match = re.search(r"(\d{1,2})\s*(?:[-–]\s*\d{1,2})?\+?\s*(?:years?|yrs)\b", requirement.text, re.I)
    if not required_match:
        return None
    # Dates alone cannot prove years in a particular skill or exclude education.
    subjects = {o.canonical for o in find_occurrences(requirement.text, [])}
    for sentence in resume.sentences:
        match = re.search(r"\b(\d{1,2})\+?\s*(?:years?|yrs)\b", sentence.text, re.I)
        evidence_subjects = {o.canonical for o in find_occurrences(sentence.text, [])}
        if match and subjects and subjects <= evidence_subjects and int(match.group(1)) >= int(required_match.group(1)):
            return _make_link(requirement, jd, resume, "contextual", CONTEXTUAL_SCORE, sentence.text, sentence.index, sentence.start, sentence.end)
    return None


def _match_soft_or_ability(requirement: Requirement, jd: ParsedDoc, resume: ParsedDoc) -> Link | None:
    requirement_tokens = set(_sig_tokens(requirement.text))
    for triggers, pattern in _SOFT_TRIGGER_PATTERNS:
        if requirement.kind != "soft":
            break
        if not triggers & requirement_tokens:
            continue
        for sentence in resume.sentences:
            match = pattern.search(sentence.text)
            if match and len(_sig_tokens(sentence.text)) >= 4:
                return _make_link(requirement, jd, resume, "contextual", CONTEXTUAL_SCORE, sentence.text, sentence.index, sentence.start, sentence.end)
    if requirement.kind != "ability":
        return None
    required_stems = {_stem(token) for token in requirement_tokens}
    required_actions = required_stems & ACTION_STEMS
    required_objects = required_stems - ACTION_STEMS - WEAK_OBJECTS
    if not required_actions or not required_objects:
        return None
    for sentence in resume.sentences:
        spans = _token_spans(sentence.text.lower())
        stemmed = [(_stem(word), start, end) for word, start, end in spans]
        action_hits = [item for item in stemmed if item[0] in required_actions]
        object_hits = [item for item in stemmed if item[0] in required_objects]
        found_objects = {item[0] for item in object_hits}
        if action_hits and required_objects <= found_objects and len(required_objects) >= 2:
            start = min(action_hits[0][1], object_hits[0][1])
            end = max(action_hits[0][2], *(item[2] for item in object_hits))
            return _make_link(requirement, jd, resume, "contextual", CONTEXTUAL_SCORE, sentence.text[start:end], sentence.index, sentence.start + start, sentence.start + end)
    return None


def match_requirements(
    requirements: list[Requirement],
    jd: ParsedDoc,
    resume: ParsedDoc,
    max_requirements: int = 24,
    **_: Any,
) -> HybridResult:
    result = HybridResult()
    for requirement in requirements[:max_requirements]:
        if _jd_anchor(requirement, jd) is None:
            continue
        row = RequirementMatchRow(
            term=requirement.text,
            kind=requirement.kind,
            required=requirement.required,
            source_text=requirement.source_text or requirement.text,
            jd_start=requirement.jd_start,
            jd_end=requirement.jd_end,
        )
        if requirement.kind == "skill":
            link = _match_skill(requirement, jd, resume)
        elif requirement.kind == "degree":
            link = _match_degree(requirement, jd, resume)
        elif requirement.kind == "years":
            link = _match_years(requirement, jd, resume)
        else:
            link = _match_soft_or_ability(requirement, jd, resume)
        if link:
            row.matched, row.quality, row.score, row.resume_term = True, link.quality, link.score, link.resume_term
            result.links.append(link)
            if requirement.required:
                result.matched_required.append(requirement.text)
        else:
            (result.missing_required if requirement.required else result.missing_optional).append(requirement.text)
        result.rows.append(row)
    result.links.sort(key=lambda link: (0 if link.required else 1, -link.score, link.canonical.lower()))
    return result


def rows_to_dicts(rows: list[RequirementMatchRow]) -> list[dict[str, Any]]:
    return [row.to_dict() for row in rows]
