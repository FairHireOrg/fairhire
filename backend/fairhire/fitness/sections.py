"""Resume section detection for the fitness rubric."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fairhire.fitness.lexicon import section_aliases as _load_aliases


def _aliases() -> dict[str, tuple[str, ...]]:
    return _load_aliases()


# Back-compat alias; prefer fairhire.fitness.lexicon.section_aliases().
SECTION_ALIASES: dict[str, tuple[str, ...]] = _load_aliases()


@dataclass
class ResumeSections:
    raw: str
    found: dict[str, bool] = field(default_factory=dict)
    bodies: dict[str, str] = field(default_factory=dict)
    headings: list[str] = field(default_factory=list)


def _normalize_heading(line: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", line)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    if stripped.endswith(":"):
        stripped = stripped[:-1].strip()
    words = stripped.split()
    if not words or len(words) > 6:
        return False
    # All-caps or Title Case short lines are typical resume headings
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio >= 0.7 or stripped.istitle() or stripped.lower() in {
        alias for aliases in SECTION_ALIASES.values() for alias in aliases
    }


def parse_sections(resume_text: str) -> ResumeSections:
    lines = resume_text.splitlines()
    heading_indexes: list[tuple[int, str, str]] = []

    for i, line in enumerate(lines):
        if not _is_heading(line):
            continue
        norm = _normalize_heading(line.rstrip(":"))
        for key, aliases in SECTION_ALIASES.items():
            if norm in aliases:
                heading_indexes.append((i, key, line.strip()))
                break

    found = {key: False for key in SECTION_ALIASES}
    bodies: dict[str, str] = {}
    headings = [h for _, _, h in heading_indexes]

    for idx, (start, key, _) in enumerate(heading_indexes):
        end = heading_indexes[idx + 1][0] if idx + 1 < len(heading_indexes) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        found[key] = True
        # Prefer first occurrence body; append if duplicate heading
        if key in bodies and bodies[key]:
            bodies[key] = bodies[key] + "\n" + body
        else:
            bodies[key] = body

    # Heuristic fallback: skills often appear as comma lists without a heading
    if not found["skills"]:
        for line in lines:
            if "," in line and len(re.findall(r"[A-Za-z][A-Za-z.+#\-]{1,20}", line)) >= 4:
                techish = sum(
                    1
                    for tok in re.findall(r"[A-Za-z][A-Za-z0-9.+#\-]{1,24}", line)
                    if tok[0].isupper() or tok.lower() in {"python", "java", "sql", "aws", "react"}
                )
                if techish >= 2:
                    found["skills"] = True
                    bodies["skills"] = line.strip()
                    break

    if not found["experience"]:
        # Dates like 2020-2023, Jan 2021, or "June 2021 – March 2024" often
        # mark experience blocks even when the heading is non-standard.
        month = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        date_hits = len(
            re.findall(
                rf"\b(?:{month}\s+)?(?:19|20)\d{{2}}\s*[-–—]\s*"
                r"(?:(?:19|20)\d{2}|present|current)\b",
                resume_text,
                flags=re.I,
            )
        ) + len(re.findall(rf"\b{month}\s+(?:19|20)\d{{2}}\b", resume_text, flags=re.I))
        if date_hits >= 1:
            found["experience"] = True
            bodies.setdefault("experience", resume_text)

    return ResumeSections(raw=resume_text, found=found, bodies=bodies, headings=headings)
