"""Deterministic skill/term ontology for NER-style matching.

Every term is matched as a *literal variant* (word-boundary, case-insensitive)
against the raw document so that character offsets stay accurate for the
frontend "matching lines" visualization. No LLM, no embeddings.

For single-word terms, the canonical form must be long enough (>3 chars) to
avoid false positives on ordinary words (e.g. "Go" the verb vs the language).
"""

from __future__ import annotations

from dataclasses import dataclass

from fairhire.fitness.lexicon import ontology_payload

CATEGORY_LABELS: dict[str, str] = dict(ontology_payload().get("category_labels", {}))


@dataclass(frozen=True)
class OntologyTerm:
    canonical: str
    variants: tuple[str, ...]
    category: str


def _t(canonical: str, category: str, *variants: str) -> OntologyTerm:
    """Build an ontology entry. Variants are literal strings as they appear in text."""
    return OntologyTerm(canonical=canonical, variants=variants or (canonical,), category=category)


def _load_terms() -> list[OntologyTerm]:
    payload = ontology_payload()
    terms: list[OntologyTerm] = []
    for entry in payload.get("terms", []):
        variants = tuple(entry.get("variants") or (entry["canonical"],))
        terms.append(OntologyTerm(canonical=entry["canonical"], variants=variants, category=entry["category"]))
    return terms


_TERMS: list[OntologyTerm] = _load_terms()

_CANONICAL_TO_TERM: dict[str, OntologyTerm] = {t.canonical: t for t in _TERMS}

# Variant (lowercased) -> canonical. First variant wins; longer variants preferred
# so "React Native" beats "React" when both could apply at the same spot.
_VARIANT_INDEX: dict[str, str] = {}
for _t_ in _TERMS:
    for _v in _t_.variants:
        key = _v.lower()
        existing = _VARIANT_INDEX.get(key)
        if existing is None or len(_v) > len(_t_.canonical):
            _VARIANT_INDEX[key] = _t_.canonical


def all_terms() -> list[OntologyTerm]:
    return list(_TERMS)


def terms_by_category() -> dict[str, list[OntologyTerm]]:
    grouped: dict[str, list[OntologyTerm]] = {}
    for t in _TERMS:
        grouped.setdefault(t.category, []).append(t)
    return grouped


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.title())
