"""Data-driven lexicon loading for the deterministic fitness pipeline.

Mutable vocabularies live in ``fitness/data/*.json`` so they can be curated
without touching code. This module loads each file once (cached) and exposes
typed accessors. Contact/date/email/phone regexes intentionally stay in code:
they are universal patterns, not resume-specific vocabulary.

NLTK English stopwords are loaded lazily (downloading the corpus on first use
when missing); the domain-noise list from ``domain_filters.json`` is unioned
with them by callers that need JD/resume noise filtering.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"

# Minimal fallback if NLTK or its stopwords corpus is unavailable (e.g. offline
# CI). Callers always union this with domain_filters, never silently shrink it.
_FALLBACK_ENGLISH_STOPWORDS = frozenset(
    "i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their "
    "theirs themselves what which who whom this that these those am is are "
    "was were be been being have has had having do does did doing a an the "
    "and but if or because as until while of at by for with about against "
    "between into through during before after above below to from up down in "
    "out on off over under again further then once here there when where why "
    "how all any both each few more most other some such no nor not only own "
    "same so than too very can will just should now".split()
)


@lru_cache(maxsize=None)
def _load_json(name: str) -> dict:
    path = _DATA_DIR / name
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Lexicon file {name} must contain a JSON object")
    return data


@lru_cache(maxsize=None)
def section_aliases() -> dict[str, tuple[str, ...]]:
    """Canonical section key -> accepted heading aliases (lowercased)."""
    raw = _load_json("section_aliases.json")
    out: dict[str, tuple[str, ...]] = {}
    for key, aliases in raw.items():
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"section_aliases.json: section {key!r} needs a non-empty alias list")
        out[str(key)] = tuple(str(a).lower() for a in aliases)
    return out


@lru_cache(maxsize=None)
def role_words() -> tuple[str, ...]:
    """Single-word role indicators used for title heuristics."""
    raw = _load_json("role_words.json")
    words = raw.get("words")
    if not isinstance(words, list) or not words:
        raise ValueError("role_words.json must contain a non-empty 'words' list")
    return tuple(str(w) for w in words)


@lru_cache(maxsize=None)
def role_words_pattern() -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in role_words()) + r")\b", re.I)


@lru_cache(maxsize=None)
def ontology_payload() -> dict:
    """Raw ontology.json payload (category_labels + terms)."""
    return _load_json("ontology.json")


@lru_cache(maxsize=None)
def domain_filter_tokens() -> frozenset[str]:
    """JD/resume noise tokens that are NOT English stopwords."""
    raw = _load_json("domain_filters.json")
    tokens = raw.get("tokens")
    if not isinstance(tokens, list):
        raise ValueError("domain_filters.json must contain a 'tokens' list")
    return frozenset(str(t).lower() for t in tokens)


@lru_cache(maxsize=None)
def soft_trigger_patterns() -> list[tuple[frozenset[str], re.Pattern[str]]]:
    """(trigger tokens, evidence regex) pairs for soft-skill matching."""
    raw = _load_json("soft_triggers.json")
    patterns = raw.get("patterns")
    if not isinstance(patterns, list):
        raise ValueError("soft_triggers.json must contain a 'patterns' list")
    out: list[tuple[frozenset[str], re.Pattern[str]]] = []
    for entry in patterns:
        triggers = frozenset(str(t).lower() for t in entry.get("triggers", []))
        pattern = re.compile(str(entry["pattern"]), re.I)
        out.append((triggers, pattern))
    return out


@lru_cache(maxsize=None)
def english_stopwords() -> frozenset[str]:
    """NLTK English stopwords, downloading the corpus on first use if needed."""
    try:
        from nltk.corpus import stopwords as nltk_stopwords

        try:
            words = nltk_stopwords.words("english")
        except LookupError:
            import nltk

            nltk.download("stopwords", quiet=True)
            words = nltk_stopwords.words("english")
        return frozenset(w.lower() for w in words)
    except Exception:
        return _FALLBACK_ENGLISH_STOPWORDS


@lru_cache(maxsize=None)
def stopwords_with_domain_filters() -> frozenset[str]:
    """NLTK English stopwords ∪ domain-noise tokens, for JD/resume filtering."""
    return english_stopwords() | domain_filter_tokens()


def ensure_nltk_data() -> None:
    """Pre-fetch NLTK corpora needed by the pipeline (safe to call at setup)."""
    try:
        import nltk

        nltk.download("stopwords", quiet=True)
    except Exception:
        pass
