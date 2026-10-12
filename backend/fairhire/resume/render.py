"""Canonical plain-text rendering of a ``Resume``.

This is the exact text an ATS would read from the exported document: one
column, standard headings, ``Title | Company | Location | Start – End``
header lines, ``-`` bullets. The scorer, the preview and the .txt export all
use it, so what the user sees is what is scored.
"""

from __future__ import annotations

from fairhire.resume.model import DEFAULT_TITLES, Entry, Resume, Section

# Headings that parsers reliably recognise. A custom title is kept only for
# the "custom" kind, which has no standard equivalent.
STANDARD_TITLES = {k: v for k, v in DEFAULT_TITLES.items() if k != "custom"}


def section_title(sec: Section) -> str:
    return STANDARD_TITLES.get(sec.kind) or sec.title or DEFAULT_TITLES["custom"]


def dates(e: Entry) -> str:
    return " – ".join(p for p in (e.start, e.end) if p)


def header_line(e: Entry) -> str:
    """One line per entry header: parsers segment entries on it."""
    return " | ".join(p for p in (e.heading, e.subheading, e.location, e.detail, e.link, dates(e)) if p)


def contact_lines(r: Resume) -> list[str]:
    c = r.contact
    out: list[str] = []
    if c.name:
        out.append(c.name)
    if c.headline:
        out.append(c.headline)
    line = " | ".join(p for p in (c.email, c.phone, c.location) if p)
    if line:
        out.append(line)
    out.extend(link for link in c.links if link)
    out.extend(o for o in c.other if o)
    return out


def render_with_map(r: Resume) -> tuple[str, list[dict[str, str]]]:
    """Canonical text plus, per physical line, which part of the document owns it.

    ``owners[i]`` is ``{"section": id | "contact" | "summary", "entry": id | ""}``
    for line ``i`` (0-based, same indexing as ``text.splitlines()``).
    """
    lines: list[str] = []
    owners: list[dict[str, str]] = []

    def add(text: str, section: str, entry: str = "") -> None:
        lines.append(text)
        owners.append({"section": section, "entry": entry})

    for text in contact_lines(r):
        add(text, "contact")
    if r.summary.strip():
        add("", "summary")
        add("Summary", "summary")
        for part in r.summary.strip().splitlines():
            add(part, "summary")
    for sec in r.sections:
        body: list[tuple[str, str]] = []
        if sec.kind == "skills":
            for g in sec.groups:
                items = ", ".join(i for i in g.items if i)
                if g.label and items:
                    body.append((f"{g.label}: {items}", ""))
                elif items or g.label:
                    body.append((items or g.label, ""))
        else:
            for e in sec.entries:
                head = header_line(e)
                if head:
                    body.append((head, e.id))
                body.extend((f"- {b}", e.id) for b in e.bullets if b.strip())
        if body:
            add("", sec.id)
            add(section_title(sec), sec.id)
            for text, eid in body:
                add(text, sec.id, eid)
    while lines and not lines[0].strip():
        lines.pop(0)
        owners.pop(0)
    return "\n".join(lines) + "\n", owners


def render_text(r: Resume) -> str:
    return render_with_map(r)[0]
