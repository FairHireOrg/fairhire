"""Canonical structured resume model for the DOCX clean-fix loop.

``ResumeDocument`` is the editable, ATS-safe representation of a resume:
contact, summary, experience, education, skills, certifications, projects.
It is populated best-effort from :func:`parse_resume`; anything the parser
cannot recover becomes an empty editor field plus an ATS recommendation.

:func:`document_to_text` renders the canonical plain-text form that is
re-scored after every edit, so the issue checklist always reflects the
current document.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from fairhire.fitness.ner import DATE_RANGE_RE, DEGREE_RE, EMAIL_RE, MONTHS, PHONE_RE, URL_RE, ParsedDoc, parse_resume

_STANDARD_HEADINGS = ("Summary", "Work Experience", "Education", "Skills", "Certifications", "Projects")


@dataclass
class Contact:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contact:
        return cls(
            name=str(data.get("name", "") or ""),
            email=str(data.get("email", "") or ""),
            phone=str(data.get("phone", "") or ""),
            location=str(data.get("location", "") or ""),
            linkedin=str(data.get("linkedin", "") or ""),
            github=str(data.get("github", "") or ""),
        )


@dataclass
class ExperienceItem:
    title: str = ""
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceItem:
        bullets = data.get("bullets") or []
        return cls(
            title=str(data.get("title", "") or ""),
            company=str(data.get("company", "") or ""),
            location=str(data.get("location", "") or ""),
            start=str(data.get("start", "") or ""),
            end=str(data.get("end", "") or ""),
            bullets=[str(b) for b in bullets if str(b).strip()],
        )


@dataclass
class EducationItem:
    degree: str = ""
    school: str = ""
    year: str = ""
    area: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EducationItem:
        return cls(
            degree=str(data.get("degree", "") or ""),
            school=str(data.get("school", "") or ""),
            year=str(data.get("year", "") or ""),
            area=str(data.get("area", "") or ""),
        )


@dataclass
class ResumeDocument:
    contact: Contact = field(default_factory=Contact)
    summary: str = ""
    experience: list[ExperienceItem] = field(default_factory=list)
    education: list[EducationItem] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact": self.contact.to_dict(),
            "summary": self.summary,
            "experience": [e.to_dict() for e in self.experience],
            "education": [e.to_dict() for e in self.education],
            "skills": list(self.skills),
            "certifications": list(self.certifications),
            "projects": list(self.projects),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResumeDocument:
        if not isinstance(data, dict):
            raise ValueError("document must be a JSON object")
        contact = data.get("contact") or {}
        return cls(
            contact=Contact.from_dict(contact) if isinstance(contact, dict) else Contact(),
            summary=str(data.get("summary", "") or ""),
            experience=[ExperienceItem.from_dict(e) for e in (data.get("experience") or []) if isinstance(e, dict)][:20],
            education=[EducationItem.from_dict(e) for e in (data.get("education") or []) if isinstance(e, dict)][:10],
            skills=[str(s).strip() for s in (data.get("skills") or []) if str(s).strip()][:100],
            certifications=[str(c).strip() for c in (data.get("certifications") or []) if str(c).strip()][:30],
            projects=[str(p).strip() for p in (data.get("projects") or []) if str(p).strip()][:30],
        )


_BULLET_LEAD_RE = re.compile(r"^\s*(?:[-*•·▪◦‣➔→⇒✓✔★☆►▸]|\d+[.)])\s*")


def _clean_ws(line: str) -> str:
    """Collapse layout artifacts (multi-space gaps, tabs) to single spaces."""
    return re.sub(r"[ \t]{2,}|\t+", " ", line).strip()


def _is_contact_line(line: str) -> bool:
    return bool(EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line))
_COMPANY_SUFFIX_RE = re.compile(
    r"^(?P<title>.+?),\s*(?P<company>[\w .&'\-]*(?:Inc|Co|LLC|Ltd|Corp|GmbH|Labs|Studio|Works)\.?)$"
)


def _strip_bullet(line: str) -> str:
    return _clean_ws(_BULLET_LEAD_RE.sub("", line))


def _split_date_range(text: str) -> tuple[str, str, str]:
    """Return (start, end, remainder) for the first date range in text."""
    m = DATE_RANGE_RE.search(text)
    if not m:
        return "", "", text
    parts = re.split(r"\s*(?:[-–—]|to)\s*", m.group(0).strip(), maxsplit=1)
    start = parts[0].strip() if parts else ""
    end = parts[1].strip() if len(parts) > 1 else ""
    remainder = (text[: m.start()] + " " + text[m.end() :]).strip(" \t|,–—-")
    return start, end, remainder


def _parse_experience_body(body: str) -> list[ExperienceItem]:
    """Best-effort split of an experience section into role items.

    A new item starts at a line carrying a date range, or a line with a
    pipe/dash separator joining title-like fragments. Bullets attach to the
    current item; anything else is carried as context for the next split.
    """
    items: list[ExperienceItem] = []
    current: ExperienceItem | None = None
    pending: list[str] = []

    def flush() -> None:
        nonlocal current
        if current and (current.title or current.company or current.bullets):
            items.append(current)
        current = None

    for raw in body.splitlines():
        line = _clean_ws(raw)
        if not line:
            continue
        if _is_contact_line(line) and not DATE_RANGE_RE.search(line):
            continue
        if _BULLET_LEAD_RE.match(raw):
            bullet = _strip_bullet(raw)
            if not bullet:
                continue
            if current is None:
                current = ExperienceItem()
                if pending:
                    current.title = pending.pop(0)
            current.bullets.append(bullet)
            continue
        start, end, remainder = _split_date_range(line)
        if start or end:
            flush()
            title, company = "", ""
            if remainder:
                parts = [p.strip() for p in re.split(r"[|–—]", remainder) if p.strip()]
                if len(parts) >= 2:
                    title, company = parts[0], parts[1]
                elif parts:
                    m = _COMPANY_SUFFIX_RE.match(parts[0])
                    if m:
                        title, company = m.group("title").strip(), m.group("company").strip()
                    else:
                        title = parts[0]
            elif pending:
                title = pending.pop(0)
            current = ExperienceItem(title=title, company=company, start=start, end=end)
            continue
        if "|" in line or re.search(r"\s{2,}", raw):
            chunks = [c.strip() for c in re.split(r"[|]|\s{2,}", line) if c.strip()]
            if len(chunks) >= 2 and any(len(c.split()) <= 8 for c in chunks[:2]):
                flush()
                current = ExperienceItem(title=chunks[0], company=chunks[1] if len(chunks) > 1 else "")
                continue
        pending.append(line)
        if len(pending) > 3:
            pending.pop(0)
    flush()
    return items[:20]


_DEGREE_PHRASE_RE = re.compile(
    r"\b(?:Bachelor|Master|Doctorate|Associate)(?:'s)?\s+of\s+(?:Science|Arts|Engineering|"
    r"Business\s+Administration|Commerce|Education| Laws|Science\s+in\s+[\w\s]+?|[\w\s]+?)(?:\s+in\s+(.+))?$",
    re.I,
)


def _parse_education_body(body: str) -> list[EducationItem]:
    items: list[EducationItem] = []
    pending_degree: EducationItem | None = None
    for raw in body.splitlines():
        line = _clean_ws(_strip_bullet(raw))
        if not line or _is_contact_line(line):
            continue
        year_m = re.search(r"\b(?:19|20)\d{2}\b", line)
        year = year_m.group(0) if year_m else ""

        # Full degree phrase first: "Bachelor of Science in Computer Science".
        phrase = _DEGREE_PHRASE_RE.search(line)
        if phrase:
            if pending_degree and (pending_degree.school or pending_degree.year):
                items.append(pending_degree)
            degree = re.sub(r"\s+", " ", phrase.group(0).strip())
            tail = line[phrase.end():].strip(" \t|,–—-.")
            area = ""
            m = re.match(r"^(?:in|of)\s+(.+)$", tail)
            if m:
                area = m.group(1).strip()
            elif phrase.group(1):
                area = phrase.group(1).strip()
            pending_degree = EducationItem(degree=degree, year=year, area=area)
            continue

        degree_m = DEGREE_RE.search(line)
        inst_m = re.search(r"\b(university|college|institute|institut|school|academy)\b", line, re.I)
        if inst_m:
            # Institution line — merge into a pending degree line or stand alone.
            school = re.sub(r"\b(?:19|20)\d{2}\b.*$", "", line).strip(" \t|,–—-.")
            if "|" in school:
                school = [p.strip(" \t|,–—-.") for p in school.split("|") if p.strip(" \t|,–—-.")][0]
            school = re.sub(rf"\b{MONTHS}\s+(?:19|20)\d{{2}}\b", "", school, flags=re.I).strip(" \t|,–—-.")
            if pending_degree and not pending_degree.school:
                pending_degree.school = school
                if year and not pending_degree.year:
                    pending_degree.year = year
                items.append(pending_degree)
                pending_degree = None
            else:
                items.append(EducationItem(school=school, year=year))
            continue

        if degree_m:
            if pending_degree and (pending_degree.school or pending_degree.year):
                items.append(pending_degree)
            remainder = (line[: degree_m.start()] + " " + line[degree_m.end():]).strip(" \t|,–—-.")
            m = re.match(r"^(?:of|in)\s+(.+)$", remainder)
            area = m.group(1).strip() if m else ""
            pending_degree = EducationItem(degree=degree_m.group(0).strip(), year=year, area=area)
            continue

        # Plain line with a year but no degree/school keyword: attach to pending.
        if year and pending_degree and not pending_degree.year:
            pending_degree.year = year
    if pending_degree and (pending_degree.degree or pending_degree.school or pending_degree.area):
        items.append(pending_degree)
    return items[:10]


def _parse_token_list(body: str) -> list[str]:
    tokens: list[str] = []
    for chunk in re.split(r"[,;|\n]", body):
        token = re.sub(r"\s+", " ", _strip_bullet(chunk)).strip()
        # Drop a heading remnant carried into heading-less fallback bodies.
        token = re.sub(r"^(?:skills|technical skills)\s+", "", token, flags=re.I)
        if len(token) >= 2:
            tokens.append(token)
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        key = token.lower()
        if key not in seen:
            seen.add(key)
            out.append(token)
    return out[:100]


def _parse_line_list(body: str) -> list[str]:
    items: list[str] = []
    for raw in body.splitlines():
        line = _strip_bullet(raw)
        if line:
            items.append(line)
    return items[:30]


def document_from_parsedoc(doc: ParsedDoc) -> ResumeDocument:
    """Best-effort mapping from a parsed resume to an editable document."""
    from fairhire.fitness.ats import _detect_name

    fields = doc.fields
    bodies = doc.section_bodies or {}
    contact = Contact(
        name=_detect_name(doc.text) or "",
        email=str(fields.get("email", "") or ""),
        phone=str(fields.get("phone", "") or ""),
        location=str(fields.get("location", "") or ""),
        linkedin=str(fields.get("linkedin", "") or ""),
        github=str(fields.get("github", "") or ""),
    )
    experience = _parse_experience_body(bodies.get("experience", ""))
    if not experience and (fields.get("date_ranges") or fields.get("titles")):
        # No headed Experience section (scrambled layout, creative labels):
        # recover roles from date/title lines across the full text.
        experience = _parse_experience_body(doc.text)
    education = _parse_education_body(bodies.get("education", ""))
    if not education and fields.get("degrees"):
        education = _parse_education_body(doc.text)
    return ResumeDocument(
        contact=contact,
        summary=bodies.get("summary", "").strip(),
        experience=experience,
        education=education,
        skills=_parse_token_list(bodies.get("skills", "")),
        certifications=_parse_line_list(bodies.get("certifications", "")),
        projects=_parse_line_list(bodies.get("projects", "")),
    )


def document_from_text(resume_text: str) -> ResumeDocument:
    return document_from_parsedoc(parse_resume(resume_text))


def document_to_text(doc: ResumeDocument) -> str:
    """Render the canonical plain-text form that is re-scored after edits."""
    lines: list[str] = []
    c = doc.contact
    if c.name:
        lines.append(c.name)
    contact_bits = [b for b in (c.email, c.phone, c.location) if b]
    if contact_bits:
        lines.append(", ".join(contact_bits))
    for link in (c.linkedin, c.github):
        if link:
            lines.append(link)
    if doc.summary:
        lines.append("")
        lines.append("Summary")
        lines.append(doc.summary.strip())
    if doc.experience:
        lines.append("")
        lines.append("Work Experience")
        for item in doc.experience:
            header = " | ".join(p for p in (item.title, item.company) if p)
            dates = " ".join(p for p in (item.start, item.end) if p)
            if dates:
                header = f"{header} | {dates}" if header else dates
            if header:
                lines.append(header)
            for bullet in item.bullets:
                if bullet.strip():
                    lines.append(f"- {bullet.strip()}")
    if doc.education:
        lines.append("")
        lines.append("Education")
        for item in doc.education:
            parts = [p for p in (item.degree, item.school, item.year) if p]
            if parts:
                lines.append(", ".join(parts))
    if doc.skills:
        lines.append("")
        lines.append("Skills")
        lines.append(", ".join(doc.skills))
    if doc.certifications:
        lines.append("")
        lines.append("Certifications")
        for cert in doc.certifications:
            lines.append(f"- {cert}")
    if doc.projects:
        lines.append("")
        lines.append("Projects")
        for proj in doc.projects:
            lines.append(f"- {proj}")
    return "\n".join(lines).strip() + "\n"
