"""Deterministic, evidence-backed matching between a JD and a resume."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fairhire.fitness.ner import ParsedDoc, TermOccurrence, term_tokens

EXACT_SCORE = 1.0
CONTEXTUAL_SCORE = 0.75
CONTAINS_SCORE = CONTEXTUAL_SCORE
FAMILY_SCORE = 0.7
MIN_MATCH_SCORE = 0.5

_CONTAINS_WINDOW = 6
_TOKEN_RE = re.compile(r"[A-Za-z0-9+#]+(?:\.[A-Za-z0-9]+)*")
_SECTION_RANK = {"skills": 4, "experience": 3, "projects": 2, "summary": 1, "education": 1}

# Reviewed relationships only. Broad prefixes made Java match JavaScript.
FAMILY_RELATIONSHIPS: dict[str, tuple[str, ...]] = {
    "SQL": ("PostgreSQL", "MySQL", "SQLite", "SQL Server", "Oracle"),
    "Spring": ("Spring Boot",),
    ".NET": ("ASP.NET",),
    "React": ("React Native",),
}


@dataclass
class Link:
    canonical: str
    jd_term: str
    resume_term: str
    category: str
    required: bool
    quality: str
    score: float
    jd_sentence_index: int
    jd_sentence_text: str
    jd_start: int
    jd_end: int
    resume_sentence_index: int
    resume_sentence_text: str
    resume_start: int
    resume_end: int
    jd_section_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "canonical": self.canonical,
            "jd_term": self.jd_term,
            "resume_term": self.resume_term,
            "category": self.category,
            "required": self.required,
            "quality": self.quality,
            "score": self.score,
            "jd_sentence_index": self.jd_sentence_index,
            "jd_sentence_text": self.jd_sentence_text,
            "jd_start": self.jd_start,
            "jd_end": self.jd_end,
            "resume_sentence_index": self.resume_sentence_index,
            "resume_sentence_text": self.resume_sentence_text,
            "resume_start": self.resume_start,
            "resume_end": self.resume_end,
        }


@dataclass
class MatchResult:
    links: list[Link] = field(default_factory=list)
    matched_required: list[str] = field(default_factory=list)
    matched_optional: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)


def _sentence_text(doc: ParsedDoc, index: int) -> str:
    return doc.sentences[index].text if 0 <= index < len(doc.sentences) else ""


def _best_resume_occurrence(resume: ParsedDoc, canonical: str) -> TermOccurrence | None:
    occurrences = resume.occurrence_map().get(canonical, [])
    if not occurrences:
        return None

    def rank(occurrence: TermOccurrence) -> int:
        for section, score in _SECTION_RANK.items():
            body = resume.section_bodies.get(section, "")
            if body and occurrence.text in body:
                return score
        return 2 if len(_sentence_text(resume, occurrence.sentence_index)) >= 20 else 0

    return max(occurrences, key=lambda occurrence: (rank(occurrence), -occurrence.start))


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(0), match.start(), match.end()) for match in _TOKEN_RE.finditer(text)]


def _contains_match(
    resume: ParsedDoc, canonical: str
) -> tuple[str, int, int, int, str] | None:
    """Find every meaningful phrase token inside one nearby sentence window."""
    tokens = term_tokens(canonical)
    if len(tokens) < 2:
        return None
    for sentence in resume.sentences:
        spans = _token_spans(sentence.text.lower())
        positions: list[int] = []
        for token in tokens:
            position = next(
                (index for index, (word, _, _) in enumerate(spans) if word.lower() == token),
                None,
            )
            if position is None:
                break
            positions.append(position)
        if len(positions) != len(tokens):
            continue
        first, last = min(positions), max(positions)
        if last - first > _CONTAINS_WINDOW:
            continue
        bridge_words = {word for word, _, _ in spans[first:last + 1]} - set(tokens)
        if not bridge_words <= {"and", "of", "for", "with", "the", "data", "backend", "large", "scale", "based"}:
            continue
        local_start = spans[first][1]
        local_end = spans[last][2]
        snippet = sentence.text[local_start:local_end]
        return snippet, sentence.index, sentence.start + local_start, sentence.start + local_end, snippet
    return None


def _family_match(
    resume: ParsedDoc, canonical: str
) -> tuple[str, int, int, int, str] | None:
    for related in FAMILY_RELATIONSHIPS.get(canonical, ()):
        occurrence = _best_resume_occurrence(resume, related)
        if occurrence is not None:
            return occurrence.variant, occurrence.sentence_index, occurrence.start, occurrence.end, occurrence.text
    return None


def link_is_valid(link: Link, jd: ParsedDoc, resume: ParsedDoc) -> bool:
    if not (0 <= link.jd_sentence_index < len(jd.sentences)):
        return False
    if not (0 <= link.resume_sentence_index < len(resume.sentences)):
        return False
    if not (0 <= link.jd_start < link.jd_end <= len(jd.text)):
        return False
    if not (0 <= link.resume_start < link.resume_end <= len(resume.text)):
        return False
    jd_sentence = jd.sentences[link.jd_sentence_index]
    resume_sentence = resume.sentences[link.resume_sentence_index]
    if not (jd_sentence.start <= link.jd_start < link.jd_end <= jd_sentence.end):
        return False
    if not (resume_sentence.start <= link.resume_start < link.resume_end <= resume_sentence.end):
        return False
    return (jd.text[link.jd_start:link.jd_end] == link.jd_term
            and resume.text[link.resume_start:link.resume_end] == link.resume_term
            and bool(link.resume_term.strip())
            and link.quality in {"exact", "contextual", "family"})


def match_documents(jd: ParsedDoc, resume: ParsedDoc) -> MatchResult:
    result = MatchResult()
    jd_by_canonical: dict[str, TermOccurrence] = {}
    for occurrence in jd.occurrences:
        jd_by_canonical.setdefault(occurrence.canonical, occurrence)

    required_set = set(jd.required_terms)
    for canonical in [*jd.required_terms, *jd.optional_terms]:
        jd_occurrence = jd_by_canonical.get(canonical)
        if jd_occurrence is None:
            continue
        required = canonical in required_set
        resume_occurrence = _best_resume_occurrence(resume, canonical)
        found: tuple[str, int, int, int, str] | None = None
        quality, score = "exact", EXACT_SCORE
        if resume_occurrence is not None:
            found = (
                resume_occurrence.variant, resume_occurrence.sentence_index,
                resume_occurrence.start, resume_occurrence.end, resume_occurrence.text,
            )
        else:
            found = _contains_match(resume, canonical)
            if found is not None:
                quality, score = "contextual", CONTEXTUAL_SCORE
            else:
                found = _family_match(resume, canonical)
                if found is not None:
                    quality, score = "family", FAMILY_SCORE

        link = None
        if found is not None:
            _, sentence_index, start, end, matched_text = found
            link = Link(
                canonical=canonical,
                jd_term=jd.text[jd_occurrence.start:jd_occurrence.end],
                resume_term=matched_text,
                category=jd_occurrence.category,
                required=required,
                quality=quality,
                score=score,
                jd_sentence_index=jd_occurrence.sentence_index,
                jd_sentence_text=_sentence_text(jd, jd_occurrence.sentence_index),
                jd_start=jd_occurrence.start,
                jd_end=jd_occurrence.end,
                resume_sentence_index=sentence_index,
                resume_sentence_text=_sentence_text(resume, sentence_index),
                resume_start=start,
                resume_end=end,
            )
            if not link_is_valid(link, jd, resume):
                link = None

        if link is not None:
            result.links.append(link)
            (result.matched_required if required else result.matched_optional).append(canonical)
        else:
            (result.missing_required if required else result.missing_optional).append(canonical)

    result.links.sort(key=lambda link: (0 if link.required else 1, -link.score, link.canonical.lower()))
    return result


def links_to_dicts(links: list[Link]) -> list[dict]:
    return [link.to_dict() for link in links]
