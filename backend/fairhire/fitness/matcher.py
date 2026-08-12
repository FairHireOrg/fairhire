"""Cross-document term matching: job description -> resume.

Produces the "matching lines" data the frontend draws between the two panes.

Deterministic matching rules, best-first:
  1. *exact*   — the same ontology term appears in both documents (highest value);
  2. *contains* — a multi-word term's significant tokens all appear within a
     nearby window of one resume sentence (contextual match);
  3. *fuzzy*   — a single long token matches a resume token within a fixed
     similarity threshold (difflib, deterministic).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from fairhire.fitness.ner import (
    ParsedDoc,
    TermOccurrence,
    term_tokens,
)

EXACT_SCORE = 1.0
CONTAINS_SCORE = 0.75
FAMILY_SCORE = 0.7
FUZZY_SCORE = 0.55
MIN_MATCH_SCORE = 0.5

_FUZZY_MIN_LEN = 6
_FUZZY_MIN_RATIO = 0.85
_CONTAINS_WINDOW = 10

_TOKEN_RE = re.compile(r"[A-Za-z0-9+#.]+")

# Preferred resume sections for picking the "best" occurrence of a matched term.
_SECTION_RANK = {"skills": 4, "experience": 3, "projects": 2, "summary": 1, "education": 1}


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
    if 0 <= index < len(doc.sentences):
        return doc.sentences[index].text
    return ""


def _best_resume_occurrence(
    resume: ParsedDoc, canonical: str
) -> TermOccurrence | None:
    occs = resume.occurrence_map().get(canonical, [])
    if not occs:
        return None

    def rank(occ: TermOccurrence) -> int:
        for section, r in _SECTION_RANK.items():
            body = resume.section_bodies.get(section, "")
            if body and body.find(occ.text) != -1:
                return r
        # Prefer occurrences inside substantive (non-header) sentences.
        sent = _sentence_text(resume, occ.sentence_index)
        if len(sent) >= 20:
            return 2
        return 0

    return max(occs, key=lambda o: (rank(o), -o.start))


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _contains_match(
    resume: ParsedDoc, canonical: str
) -> tuple[str, int, int, int, str] | None:
    """Return (matched_snippet, sentence_index, start, end, variant) if all
    significant tokens of `canonical` appear near each other in one sentence."""
    tokens = term_tokens(canonical)
    if len(tokens) < 2:
        return None

    for sentence in resume.sentences:
        spans = _token_spans(sentence.text.lower())
        positions: list[int] = []
        for tok in tokens:
            for idx, (word, _, _) in enumerate(spans):
                if word.lower() == tok:
                    positions.append(idx)
                    break
        if len(positions) == len(tokens):
            start_idx = min(positions)
            end_idx = max(positions)
            if end_idx - start_idx > _CONTAINS_WINDOW:
                continue
            _, s_start, _ = spans[start_idx]
            _, _, s_end = spans[end_idx]
            snippet = sentence.text[s_start - sentence.start : s_end - sentence.start]
            return snippet, sentence.index, s_start, s_end, " ".join(tokens)
    return None


def _family_match(
    resume: ParsedDoc, canonical: str
) -> tuple[str, int, int, int, str] | None:
    """A JD term is often a *family* of the resume's more specific skill.

    E.g. JD "SQL" matches resume "PostgreSQL"/"MySQL"; JD "Spring" matches
    resume "Spring Boot". Only applied for single-token terms and only when
    the resume term starts-with or ends-with the JD term (deterministic).
    """
    key = re.sub(r"[^a-z0-9]", "", canonical.lower())
    if not key:
        return None
    if len(key) < 4 and key != "sql":
        return None

    for occ in resume.occurrences:
        tok = re.sub(r"[^a-z0-9]", "", occ.text.lower())
        if not tok or len(tok) < len(key):
            continue
        if key == "sql":
            if tok.startswith("sql") or tok.endswith("sql"):
                return occ.variant, occ.sentence_index, occ.start, occ.end, occ.text
        elif tok.startswith(key) or tok.endswith(key):
            return occ.variant, occ.sentence_index, occ.start, occ.end, occ.text
    return None


def _fuzzy_match(resume: ParsedDoc, canonical: str) -> tuple[str, int, int, int, str] | None:
    """Single long token matched to a resume token by similarity."""
    if len(canonical) < _FUZZY_MIN_LEN:
        return None
    cleaned = re.sub(r"[\s#+.]", "", canonical).lower()
    if len(cleaned) < _FUZZY_MIN_LEN:
        return None

    for sentence in resume.sentences:
        for word, start, end in _token_spans(sentence.text):
            word_clean = word.lower()
            if len(word_clean) < 5:
                continue
            ratio = SequenceMatcher(None, cleaned, word_clean).ratio()
            if ratio >= _FUZZY_MIN_RATIO:
                return word, sentence.index, start, end, word
    return None


def match_documents(jd: ParsedDoc, resume: ParsedDoc) -> MatchResult:
    result = MatchResult()

    def build_link(
        canonical: str,
        jd_occ: TermOccurrence,
        resume_occ: TermOccurrence | None,
        quality: str,
        score: float,
        resume_term: str,
        resume_sentence_index: int,
        resume_start: int,
        resume_end: int,
        required: bool,
    ) -> Link | None:
        jd_sent = _sentence_text(jd, jd_occ.sentence_index)
        resume_sent = _sentence_text(resume, resume_sentence_index)
        if not jd_sent.strip():
            return None
        return Link(
            canonical=canonical,
            jd_term=jd_occ.variant,
            resume_term=resume_term,
            category=jd_occ.category,
            required=required,
            quality=quality,
            score=score,
            jd_sentence_index=jd_occ.sentence_index,
            jd_sentence_text=jd_sent,
            jd_start=jd_occ.start,
            jd_end=jd_occ.end,
            resume_sentence_index=resume_sentence_index,
            resume_sentence_text=resume_sent,
            resume_start=resume_start,
            resume_end=resume_end,
        )

    # Only the first (best) occurrence of each JD term needs a link; we use the
    # occurrence inside the required/optional zone.
    jd_by_canonical: dict[str, TermOccurrence] = {}
    for occ in jd.occurrences:
        jd_by_canonical.setdefault(occ.canonical, occ)

    required_set = set(jd.required_terms)
    for canonical in [*jd.required_terms, *jd.optional_terms]:
        jd_occ = jd_by_canonical[canonical]
        required = canonical in required_set

        exact = _best_resume_occurrence(resume, canonical)
        if exact is not None:
            link = build_link(
                canonical, jd_occ, exact, "exact", EXACT_SCORE,
                exact.variant, exact.sentence_index, exact.start, exact.end, required,
            )
            if link:
                result.links.append(link)
                (result.matched_required if required else result.matched_optional).append(canonical)
            continue

        contains = _contains_match(resume, canonical)
        if contains is not None:
            snippet, sent_idx, s_start, s_end, variant = contains
            link = build_link(
                canonical, jd_occ, None, "contains", CONTAINS_SCORE,
                variant, sent_idx, s_start, s_end, required,
            )
            if link:
                result.links.append(link)
                (result.matched_required if required else result.matched_optional).append(canonical)
            continue

        family = _family_match(resume, canonical)
        if family is not None:
            variant, sent_idx, s_start, s_end, matched_text = family
            link = build_link(
                canonical, jd_occ, None, "family", FAMILY_SCORE,
                matched_text, sent_idx, s_start, s_end, required,
            )
            if link:
                result.links.append(link)
                (result.matched_required if required else result.matched_optional).append(canonical)
            continue

        fuzzy = _fuzzy_match(resume, canonical)
        if fuzzy is not None:
            word, sent_idx, s_start, s_end, variant = fuzzy
            link = build_link(
                canonical, jd_occ, None, "fuzzy", FUZZY_SCORE,
                variant, sent_idx, s_start, s_end, required,
            )
            if link:
                result.links.append(link)
                (result.matched_required if required else result.matched_optional).append(canonical)
            continue

        if required:
            result.missing_required.append(canonical)
        else:
            result.missing_optional.append(canonical)

    # Deterministic order: required first, then higher score, then term.
    result.links.sort(
        key=lambda lnk: (0 if lnk.required else 1, -lnk.score, lnk.canonical.lower())
    )
    return result


def links_to_dicts(links: list[Link]) -> list[dict]:
    return [lnk.to_dict() for lnk in links]
