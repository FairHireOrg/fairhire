"""Canonical resume model.

One shape for everything the editor, the parser, the scorer and the exporters
touch. Every section is ``Entry`` based except skills, so unknown sections are
preserved instead of dropped: the parser never silently discards a line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KINDS = ("experience", "education", "projects", "skills", "publications", "certifications", "awards", "custom")

DEFAULT_TITLES = {
    "experience": "Work Experience",
    "education": "Education",
    "projects": "Projects",
    "skills": "Skills",
    "publications": "Publications",
    "certifications": "Certifications",
    "awards": "Awards",
    "custom": "Additional",
}


def _s(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _strs(values: Any, limit: int = 200) -> list[str]:
    if not isinstance(values, list):
        return []
    return [t for t in (_s(v) for v in values) if t][:limit]


@dataclass
class Contact:
    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "headline": self.headline, "email": self.email, "phone": self.phone,
            "location": self.location, "links": list(self.links), "other": list(self.other),
        }

    @classmethod
    def from_dict(cls, d: Any) -> Contact:
        d = d if isinstance(d, dict) else {}
        return cls(
            name=_s(d.get("name")), headline=_s(d.get("headline")), email=_s(d.get("email")),
            phone=_s(d.get("phone")), location=_s(d.get("location")),
            links=_strs(d.get("links"), 12), other=_strs(d.get("other"), 12),
        )


@dataclass
class Entry:
    id: str = ""
    heading: str = ""        # job title / degree / project name / item name
    subheading: str = ""     # company / school / publisher
    location: str = ""
    start: str = ""
    end: str = ""
    link: str = ""
    detail: str = ""         # GPA, tech used, honours: single-line extras
    bullets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "heading": self.heading, "subheading": self.subheading,
            "location": self.location, "start": self.start, "end": self.end,
            "link": self.link, "detail": self.detail, "bullets": list(self.bullets),
        }

    @classmethod
    def from_dict(cls, d: Any, fallback_id: str = "") -> Entry:
        d = d if isinstance(d, dict) else {}
        return cls(
            id=_s(d.get("id")) or fallback_id, heading=_s(d.get("heading")),
            subheading=_s(d.get("subheading")), location=_s(d.get("location")),
            start=_s(d.get("start")), end=_s(d.get("end")), link=_s(d.get("link")),
            detail=_s(d.get("detail")), bullets=_strs(d.get("bullets"), 40),
        )

    def is_empty(self) -> bool:
        return not any((self.heading, self.subheading, self.location, self.start, self.end,
                        self.link, self.detail, self.bullets))


@dataclass
class SkillGroup:
    label: str = ""
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "items": list(self.items)}

    @classmethod
    def from_dict(cls, d: Any) -> SkillGroup:
        d = d if isinstance(d, dict) else {}
        return cls(label=_s(d.get("label")), items=_strs(d.get("items"), 100))


@dataclass
class Section:
    id: str = ""
    kind: str = "custom"
    title: str = ""
    entries: list[Entry] = field(default_factory=list)
    groups: list[SkillGroup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind, "title": self.title,
            "entries": [e.to_dict() for e in self.entries],
            "groups": [g.to_dict() for g in self.groups],
        }

    @classmethod
    def from_dict(cls, d: Any, fallback_id: str = "") -> Section:
        d = d if isinstance(d, dict) else {}
        kind = _s(d.get("kind"))
        if kind not in KINDS:
            kind = "custom"
        sid = _s(d.get("id")) or fallback_id
        entries = [Entry.from_dict(e, f"{sid}-e{i}") for i, e in enumerate(d.get("entries") or []) if isinstance(e, dict)]
        return cls(
            id=sid, kind=kind, title=_s(d.get("title")) or DEFAULT_TITLES[kind],
            entries=entries[:40],
            groups=[SkillGroup.from_dict(g) for g in (d.get("groups") or []) if isinstance(g, dict)][:20],
        )


@dataclass
class Resume:
    contact: Contact = field(default_factory=Contact)
    summary: str = ""
    sections: list[Section] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact": self.contact.to_dict(), "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, d: Any) -> Resume:
        if not isinstance(d, dict):
            raise ValueError("document must be a JSON object")
        sections = [Section.from_dict(s, f"s{i}") for i, s in enumerate(d.get("sections") or []) if isinstance(s, dict)]
        return cls(contact=Contact.from_dict(d.get("contact")), summary=_s(d.get("summary")), sections=sections[:20])
