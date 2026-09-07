"""Deterministic NER-style parser for resumes and job descriptions.

Combines:
  * rule + regex extraction for *structured* fields (email, phone, dates,
    URLs, degrees) — these must be exact;
  * a curated ontology matcher for *skills/terms* — token-classification style
    tagging against the raw document, so character offsets stay exact and the
    frontend can draw connecting lines.

No LLMs. No embeddings. Fully deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fairhire.fitness.ontology import all_terms
from fairhire.fitness.sections import parse_sections

MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"
)
URL_RE = re.compile(
    r"(?:https?://|www\.)?(linkedin\.com/in/[\w\-/]+|github\.com/[\w\-.]+|"
    r"https?://[\w\-.]+(?:\.[\w\-.]+)+[\w\-./?%=&]*|www\.[\w\-.]+(?:\.[\w\-.]+)+[\w\-./?%=&]*)"
)
DATE_RANGE_RE = re.compile(
    rf"\b(?:{MONTHS}\s+)?(?:19|20)\d{{2}}\s*(?:[-–—]|to)\s*"
    rf"(?:(?:{MONTHS}\s+)?(?:19|20)\d{{2}}|Present|Current|Now)\b",
    re.I,
)
DEGREE_RE = re.compile(
    r"\b(?:B\.?S\.?|B\.?A\.?|B\.?Eng\.?|M\.?S\.?|M\.?A\.?|M\.?Eng\.?|"
    r"M\.?B\.?A\.?|Ph\.?D\.?|PhD|BS|BA|MS|MA|MBA|BSc|MSc|"
    r"Bachelor(?:'s)?|Master(?:'s)?|Doctorate|Associate(?:'s)?|Engineering|"
    r"Bachelor of Science|Bachelor of Arts|Master of Science|Master of Arts)\b",
    re.I,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\b[A-Z]\.)(?<!\b[A-Z]\.[A-Z]\.)\s+")
_BULLET_LEAD = re.compile(r"^\s*(?:[-*•·▪◦‣]|\d+[.)])\s*")

# JD zone markers ------------------------------------------------------------

_ROLE_START_MARKERS = re.compile(
    r"\b(the role|about the role|about this role|job description|responsibilities|"
    r"what you(?:'|’)?ll do|what you(?:'|’)?ll be doing|requirements|qualifications|"
    r"what we look for|we(?:'|’)?re looking for|who we(?:'|’)re looking for|"
    r"what we(?:'|’)?re looking for|must haves?|essential requirements|"
    r"the job|the position|we are looking for)\b",
    re.I,
)
_OPTIONAL_START_MARKERS = re.compile(
    r"\b(nice to haves?|nice-to-haves?|bonus|preferred|plus(?: points)?|"
    r"not required|not necessary|good to haves?|we(?:'|’)d love|"
    r"bonus points for|is a plus|are a plus|even better if)\b",
    re.I,
)
_BENEFITS_END_MARKERS = re.compile(
    r"\b(benefits?|perks?|compensation|salary|equal opportunity|e-verify|"
    r"what we offer|why you(?:'|’)ll love)\b",
    re.I,
)


@dataclass
class Span:
    start: int
    end: int
    text: str

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class Sentence:
    index: int
    text: str
    start: int
    end: int


@dataclass
class TermOccurrence:
    canonical: str
    variant: str
    category: str
    sentence_index: int
    start: int
    end: int
    quality: float = 1.0
    text: str = ""


@dataclass
class ParsedDoc:
    text: str
    sentences: list[Sentence] = field(default_factory=list)
    occurrences: list[TermOccurrence] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    optional_terms: list[str] = field(default_factory=list)
    fields: dict[str, str | list[str]] = field(default_factory=dict)
    sections: dict[str, bool] = field(default_factory=dict)
    section_bodies: dict[str, str] = field(default_factory=dict)
    title: str | None = None

    def occurrence_map(self) -> dict[str, list[TermOccurrence]]:
        grouped: dict[str, list[TermOccurrence]] = {}
        for occ in self.occurrences:
            grouped.setdefault(occ.canonical, []).append(occ)
        return grouped


# ---------------------------------------------------------------------------
# Sentence segmentation (offset-accurate)
# ---------------------------------------------------------------------------


def segment_sentences(text: str) -> list[Sentence]:
    """Split text into sentences with absolute offsets.

    Each physical line becomes one or more sentences; bullets stay whole.
    """
    sentences: list[Sentence] = []
    cursor = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_start = cursor
        cursor += len(raw_line)
        stripped = line.strip()
        if not stripped:
            continue
        leading = len(line) - len(line.lstrip())
        content_start = line_start + leading
        if _BULLET_LEAD.match(line):
            sentences.append(
                Sentence(
                    len(sentences), stripped, content_start, content_start + len(stripped)
                )
            )
            continue
        # Split long prose lines on sentence boundaries.
        parts = _SENTENCE_SPLIT.split(line)
        search_from = 0
        for part in parts:
            if not part.strip():
                continue
            local = line.find(part, search_from)
            if local < 0:
                local = search_from
            trimmed = part.strip()
            part_leading = len(part) - len(part.lstrip())
            p_start = line_start + local + part_leading
            p_end = p_start + len(trimmed)
            sentences.append(Sentence(len(sentences), trimmed, p_start, p_end))
            search_from = local + len(part)
    return sentences


def _sentence_for(sentences: list[Sentence], start: int) -> int:
    for i, s in enumerate(sentences):
        if s.start <= start < max(s.end, s.start + 1):
            return i
    return -1


# ---------------------------------------------------------------------------
# Term tagging (token-classification style, over the raw text)
# ---------------------------------------------------------------------------


def _word_boundary(pattern: str) -> str:
    """Word-boundary wrap that still works for terms ending in non-word chars."""
    return rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"


def _regex_for_variant(variant: str) -> re.Pattern[str]:
    return re.compile(
        _word_boundary(re.escape(variant).replace(r"\ ", r"[\s]+")), re.I
    )


def find_occurrences(text: str, sentences: list[Sentence]) -> list[TermOccurrence]:
    """Tag every ontology term that appears in the text, with exact spans.

    Longer variants win at the same start offset (e.g. "React Native" over
    "React"), and spans are never double-counted.
    """
    # variant -> (canonical, category)
    lookup: dict[str, tuple[str, str]] = {
        v.lower(): (t.canonical, t.category)
        for t in all_terms()
        for v in t.variants
    }
    # Build a combined matcher: iterate variants longest-first.
    variants = sorted(
        ((t.canonical, t.category, v) for t in all_terms() for v in t.variants),
        key=lambda item: len(item[2]),
        reverse=True,
    )

    occupied: list[tuple[int, int, str]] = []  # (start, end, canonical)
    occurrences: list[TermOccurrence] = []

    for canonical, category, variant in variants:
        key = variant.lower()
        if lookup.get(key) != (canonical, category):
            continue
        pattern = _regex_for_variant(variant)
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            if any(s < end and e > start for s, e, _ in occupied):
                continue
            occupied.append((start, end, canonical))
            occurrences.append(
                TermOccurrence(
                    canonical=canonical,
                    variant=variant,
                    category=category,
                    sentence_index=_sentence_for(sentences, start),
                    start=start,
                    end=end,
                    text=m.group(0),
                )
            )

    occurrences.sort(key=lambda o: (o.sentence_index, o.start))
    return occurrences


def _all_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9+#.]+", text.lower())


# ---------------------------------------------------------------------------
# Structured field extraction
# ---------------------------------------------------------------------------


def extract_fields(resume_text: str) -> dict[str, str | list[str]]:
    fields: dict[str, str | list[str]] = {}

    emails = EMAIL_RE.findall(resume_text)
    if emails:
        fields["email"] = emails[0]
    else:
        fields["email"] = ""

    phones = PHONE_RE.findall(resume_text)
    if phones:
        fields["phone"] = phones[0]
    else:
        fields["phone"] = ""

    urls: list[str] = []
    for m in URL_RE.finditer(resume_text):
        u = m.group(0)
        if u not in urls:
            urls.append(u)
    fields["urls"] = urls

    linkedin = next((u for u in urls if "linkedin" in u.lower()), "")
    github = next((u for u in urls if "github" in u.lower()), "")
    if linkedin:
        fields["linkedin"] = linkedin
    if github:
        fields["github"] = github

    # Location: try to capture "City, ST" or "City, State" lines near the top.
    loc_re = re.compile(r"\b[A-Z][A-Za-z .\-]{1,30},\s*[A-Z]{2}\b|\b[A-Z][A-Za-z .\-]{1,30},\s*[A-Z][A-Za-z]{2,}\b")
    m = loc_re.search(resume_text[:1200])
    if m:
        fields["location"] = m.group(0).strip()

    date_ranges = DATE_RANGE_RE.findall(resume_text)
    fields["date_ranges"] = [d.strip() for d in date_ranges[:40]]

    degrees = DEGREE_RE.findall(resume_text)
    if degrees:
        fields["degrees"] = list(dict.fromkeys(d.strip() for d in degrees))[:8]
    else:
        fields["degrees"] = []

    return fields


# ---------------------------------------------------------------------------
# JD zone classification (which terms are required vs nice-to-have)
# ---------------------------------------------------------------------------


def classify_jd_terms(
    text: str, occurrences: list[TermOccurrence]
) -> tuple[list[str], list[str]]:
    """Deterministically split terms into required / optional.

    A term is *required* when it appears in the role zone (from the first
    role/requirements marker, or the document start, up to the first
    nice-to-have/bonus marker). A term is *optional* when it only appears
    after that optional marker.
    """
    opt_hits = list(_OPTIONAL_START_MARKERS.finditer(text))
    opt_start = opt_hits[0].start() if opt_hits else len(text)

    role_hits = list(_ROLE_START_MARKERS.finditer(text))
    role_start = role_hits[0].start() if role_hits else 0

    # Drop terms that only show up in the preamble before the role zone
    # unless they also appear inside the role zone.
    required: set[str] = set()
    optional: set[str] = set()
    by_canonical: dict[str, list[TermOccurrence]] = {}
    for occ in occurrences:
        by_canonical.setdefault(occ.canonical, []).append(occ)

    for canonical, occs in by_canonical.items():
        in_required_zone = any(role_start <= o.start < opt_start for o in occs)
        in_optional_zone = any(o.start >= opt_start for o in occs)
        if in_required_zone:
            required.add(canonical)
        elif in_optional_zone:
            optional.add(canonical)

    return _ordered_unique(required, occurrences), _ordered_unique(optional, occurrences)


def _ordered_unique(terms: set[str], occurrences: list[TermOccurrence]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for occ in occurrences:
        if occ.canonical in terms and occ.canonical not in seen:
            seen.add(occ.canonical)
            out.append(occ.canonical)
    for t in terms:
        if t not in seen:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Document-level parse entry points
# ---------------------------------------------------------------------------


def parse_job_description(jd_text: str) -> ParsedDoc:
    text = jd_text
    sentences = segment_sentences(text)
    occurrences = find_occurrences(text, sentences)
    required, optional = classify_jd_terms(text, occurrences)

    title = _extract_job_title(text)

    doc = ParsedDoc(
        text=text,
        sentences=sentences,
        occurrences=occurrences,
        required_terms=required,
        optional_terms=optional,
        title=title,
    )
    doc.fields = extract_fields(text)
    return doc


def parse_resume(resume_text: str) -> ParsedDoc:
    text = resume_text
    sentences = segment_sentences(text)
    occurrences = find_occurrences(text, sentences)
    sections = parse_sections(text)
    fields = extract_fields(text)
    fields["titles"] = _extract_role_titles(text)

    titles = fields.get("titles") or []
    if not isinstance(titles, list):
        titles = []

    doc = ParsedDoc(
        text=text,
        sentences=sentences,
        occurrences=occurrences,
        fields=fields,
        sections=sections.found,
        section_bodies=sections.bodies,
        title=titles[0] if titles else None,
    )
    return doc


# ---------------------------------------------------------------------------
# Title heuristics (deterministic, keep for role framing)
# ---------------------------------------------------------------------------


_ROLE_WORDS = re.compile(
    r"\b(engineer|developer|manager|analyst|designer|scientist|intern|"
    r"instructor|trainer|architect|consultant|founder|lead|researcher|"
    r"director|specialist|administrator|coordinator|associate)\b",
    re.I,
)
_ROLE_LINE_SKIP = re.compile(r"(@|https?://|linkedin|github|gmail|\.com\b)", re.I)
_ROLE_HEADER_SKIP = re.compile(
    r"^(about|benefits?|responsibilities|requirements?|qualifications|"
    r"what |the role|overview|job description|skills|experience|education)\b",
    re.I,
)


def _extract_job_title(jd_text: str) -> str | None:
    lines = [ln.strip() for ln in jd_text.splitlines() if ln.strip()]
    for line in lines[:50]:
        if _ROLE_HEADER_SKIP.search(line):
            continue
        if _ROLE_WORDS.search(line) and len(line) <= 90 and len(line.split()) <= 12:
            if not _ROLE_LINE_SKIP.search(line):
                return re.split(r"[.]", line)[0].strip(" ·|–—:")[:90]
    return None


def _extract_role_titles(resume_text: str) -> list[str]:
    """Pull likely role lines from the resume (date-aligned or role-word lines)."""
    date_tail = re.compile(
        rf"(?P<title>.+?)\s{{2,}}"
        rf"(?:{MONTHS}[a-z]*\.?\s+)?"
        r"(?:19|20)\d{2}\s*[-–—]\s*"
        rf"(?:(?:{MONTHS}[a-z]*\.?\s+)?(?:19|20)\d{{2}}|Present|Current)",
        re.I,
    )
    titles: list[str] = []
    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 120 or _ROLE_LINE_SKIP.search(stripped):
            continue
        m = date_tail.search(stripped)
        if m and _ROLE_WORDS.search(m.group("title")):
            titles.append(m.group("title").strip(" ·|-–—"))
            continue
        if _ROLE_WORDS.search(stripped) and len(stripped.split()) <= 10 and not stripped.endswith("."):
            left = re.split(r"[|–—]", stripped)[0].strip()
            if left:
                titles.append(left)

    seen: set[str] = set()
    out: list[str] = []
    for t in titles:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out[:12]


# ---------------------------------------------------------------------------
# Helpers re-exported for backward compatibility
# ---------------------------------------------------------------------------


def normalize_for_match(text: str) -> str:
    """Light normalization for labels only, never for source spans."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def term_tokens(canonical: str) -> list[str]:
    """Significant tokens of a term, for 'contains' sentence matching."""
    toks = _all_tokens(canonical)
    stop = {"and", "for", "with", "of", "in", "the", "systems"}
    return [t for t in toks if t not in stop]
