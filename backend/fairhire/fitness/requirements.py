"""Versioned, source-anchored checklists. AI is never on the scoring path."""

from __future__ import annotations

import hashlib
import re

from fairhire.fitness.llm_extract import Requirement
from fairhire.fitness.ner import ParsedDoc, find_occurrences

RULESET_VERSION = "2026-09-06.1"
_REQUIRED = re.compile(r"^(?:required|requirements?|qualifications?|essential|must.have|responsibilities|what you.ll do|what you.ll bring|minimum qualifications)\b", re.I)
_PREFERRED = re.compile(r"^(?:preferred|nice.to.have|bonus|desirable|optional)\b", re.I)
_IGNORE = re.compile(r"^(?:benefits?|perks?|compensation|salary|equal opportunity|about us|about the company|what we offer)\b", re.I)
_CUE = re.compile(r"\b(?:experience|proficien\w*|knowledge|familiar\w*|must|required|ability|degree|years?|skills?|develop|build|design|maintain|collaborate|manage|lead|implement|test|debug)\b", re.I)
_SOFT = re.compile(r"\b(?:communication|teamwork|collaboration|leadership|problem.solving|analytical|organizational)\b", re.I)
_DEGREE = re.compile(r"\b(?:bachelor|master|doctorate|ph\.?d|degree|b\.?s\.?|m\.?s\.?)\b", re.I)
_YEARS = re.compile(r"\b\d{1,2}\s*(?:[-–]\s*\d{1,2})?\+?\s*(?:years?|yrs)\b", re.I)


def requirement_id(requirement: Requirement) -> str:
    value = f"{requirement.kind}|{requirement.text.casefold()}|{requirement.jd_start}|{requirement.jd_end}"
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def checklist_id(requirements: list[Requirement]) -> str:
    value = RULESET_VERSION + "|" + "|".join(
        f"{requirement_id(r)}:{r.required}" for r in requirements
    )
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def extract_checklist(jd: ParsedDoc) -> list[Requirement]:
    """Keep unknown requirement statements visible instead of silently dropping them.

    Lists of technology names split into atomic concepts. Constraints, alternatives,
    and responsibilities remain whole so one technology cannot satisfy a sentence.
    """
    rows: list[Requirement] = []
    active, required = False, True
    has_headings = any(_REQUIRED.search(s.text.strip(" -*•:")) or _PREFERRED.search(s.text.strip(" -*•:")) for s in jd.sentences)
    for sentence in jd.sentences:
        text = sentence.text.strip(" -*•:")
        if _IGNORE.search(text):
            active = False
            continue
        heading = _REQUIRED.search(text) or _PREFERRED.search(text)
        if heading:
            active = True
            required = not bool(_PREFERRED.search(text))
            if len(text.split()) <= 4 and ":" not in sentence.text and not find_occurrences(text, []):
                continue
        if not active and has_headings:
            continue
        if not active and not _CUE.search(text) and not find_occurrences(text, []):
            continue
        if len(text) < 2 or (sentence.index == 0 and text == jd.title):
            continue
        optional_inline = bool(re.search(r"\b(?:preferred|nice.to.have|is a plus|not required|bonus)\b", text, re.I))
        importance = required and not optional_inline
        occurrences = find_occurrences(sentence.text, [])
        constrained = _DEGREE.search(text) or _YEARS.search(text) or re.search(r"\b(?:or|either|develop|build|design|maintain|lead|manage|implement|test|debug|collaborate)\b", text, re.I)
        if occurrences and not constrained and not _SOFT.search(text):
            for occurrence in occurrences:
                rows.append(Requirement(occurrence.canonical, "skill", importance, occurrence.text,
                                        sentence.start + occurrence.start, sentence.start + occurrence.end))
        else:
            kind = "degree" if _DEGREE.search(text) else "years" if _YEARS.search(text) else "soft" if _SOFT.search(text) else "ability"
            start = sentence.start + len(sentence.text) - len(sentence.text.lstrip(" -*•:"))
            source = jd.text[start:sentence.end]
            rows.append(Requirement(source, kind, importance, source, start, sentence.end))
    # Required wins duplicates; preserve source order and stable IDs.
    unique: dict[tuple[str, str], Requirement] = {}
    for row in rows:
        key = (row.kind, row.text.casefold())
        if key not in unique or (row.required and not unique[key].required):
            unique[key] = row
    return sorted(unique.values(), key=lambda r: (r.jd_start, r.text.casefold()))


def validate_checklist(raw: object, jd: ParsedDoc) -> list[Requirement]:
    if not isinstance(raw, list) or len(raw) > 200:
        raise ValueError("Requirements must be a list of at most 200 source-backed items.")
    output: list[Requirement] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid requirement item.")
        start, end = item.get("jd_start"), item.get("jd_end")
        source, concept = item.get("source_text"), item.get("text", item.get("term"))
        kind, required = item.get("kind"), item.get("required")
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(jd.text)
                or source != jd.text[start:end] or not isinstance(concept, str)
                or not concept.strip() or len(concept) > 2000 or type(required) is not bool
                or kind not in {"skill", "degree", "years", "soft", "ability"}):
            raise ValueError("Each requirement must reference an exact phrase in this job description.")
        if not any(s.start <= start < end <= s.end for s in jd.sentences):
            raise ValueError("A requirement must fit within one source sentence or bullet.")
        # A model cannot label 'Python' as 'Java' while quoting a real source.
        source_terms = {o.canonical for o in find_occurrences(source, [])}
        if kind == "skill":
            concept_terms = find_occurrences(concept, [])
            if len(concept_terms) != 1 or concept_terms[0].canonical not in source_terms:
                raise ValueError("Skill concepts must be supported by a recognized term in their source.")
            concept = concept_terms[0].canonical
        else:
            concept = source  # verification uses the complete literal constraint
        row = Requirement(concept, kind, required, source, start, end)
        key = requirement_id(row)
        if key not in seen:
            seen.add(key)
            output.append(row)
    return sorted(output, key=lambda r: (r.jd_start, r.text.casefold()))
