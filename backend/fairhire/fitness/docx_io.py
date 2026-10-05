"""DOCX ingest and ATS-safe export for the resume clean-fix loop.

Ingest reads ``.docx`` uploads in paragraph order (preferred over PDF text
extraction when available). Export renders a :class:`ResumeDocument` with a
template that enforces parser-safe structure: single column, contact block at
the top, standard headings, ``Month YYYY`` dates, plain ``-`` bullets, skills
as comma-separated tokens, no tables or images.
"""

from __future__ import annotations

import io
import re
from typing import Any

from fairhire.fitness.document import ResumeDocument

_DATE_FIX_RE = re.compile(r"\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|Present|Current|Now)\b")


def _normalize_date(text: str) -> str:
    """Best-effort rewrite of bare year ranges to 'Month YYYY' shape.

    Bare years carry no month, so they become ``YYYY – YYYY`` with an
    explicit separator; fully missing dates are left empty for the editor
    and the ``mixed_dates`` / ``no_dates`` recommendations to catch.
    """
    return _DATE_FIX_RE.sub(r"\1 – \2", text)


def read_docx_text(data: bytes) -> str:
    """Extract plain text from .docx bytes, preserving paragraph order."""
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(data))
    parts: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        try:
            style_name = (para.style.name or "").lower()
        except Exception:
            style_name = ""
        if "list" in style_name or "bullet" in style_name:
            text = "- " + text
        parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("No text extracted from the .docx file")
    return text


def export_document_docx(doc: ResumeDocument) -> bytes:
    """Render an ATS-safe single-column .docx from a ResumeDocument."""
    from docx import Document as DocxDocument
    from docx.shared import Pt

    out = DocxDocument()
    style = out.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    c = doc.contact
    if c.name:
        title = out.add_heading(c.name.strip(), level=0)
        for run in title.runs:
            run.font.size = Pt(20)
    contact_bits = [b for b in (c.email, c.phone, c.location) if b]
    if contact_bits:
        out.add_paragraph(" | ".join(contact_bits))
    for link in (c.linkedin, c.github):
        if link:
            out.add_paragraph(link)

    if doc.summary.strip():
        out.add_heading("Summary", level=1)
        out.add_paragraph(doc.summary.strip())

    if doc.experience:
        out.add_heading("Work Experience", level=1)
        for item in doc.experience:
            header = " | ".join(p for p in (item.title.strip(), item.company.strip()) if p)
            dates = " – ".join(p for p in (_normalize_date(item.start.strip()),
                                           _normalize_date(item.end.strip())) if p)
            if dates:
                header = f"{header} — {dates}" if header else dates
            if header:
                para = out.add_paragraph()
                run = para.add_run(header)
                run.bold = True
            for bullet in item.bullets:
                if bullet.strip():
                    out.add_paragraph(bullet.strip(), style="List Bullet")

    if doc.education:
        out.add_heading("Education", level=1)
        for item in doc.education:
            parts = [p for p in (item.degree.strip(), item.school.strip(), item.year.strip()) if p]
            if parts:
                out.add_paragraph(", ".join(parts))

    if doc.skills:
        out.add_heading("Skills", level=1)
        out.add_paragraph(", ".join(s for s in doc.skills if s.strip()))

    if doc.certifications:
        out.add_heading("Certifications", level=1)
        for cert in doc.certifications:
            if cert.strip():
                out.add_paragraph(cert.strip(), style="List Bullet")

    if doc.projects:
        out.add_heading("Projects", level=1)
        for proj in doc.projects:
            if proj.strip():
                out.add_paragraph(proj.strip(), style="List Bullet")

    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def export_jsonresume_docx(resume: dict[str, Any]) -> bytes:
    """Render a JSON Resume schema document as an ATS-safe single-column .docx."""
    from docx import Document as DocxDocument
    from docx.shared import Pt

    out = DocxDocument()
    style = out.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    basics = resume.get("basics") or {}
    name = str(basics.get("name") or "").strip()
    if name:
        title = out.add_heading(name, level=0)
        for run in title.runs:
            run.font.size = Pt(20)
    label = str(basics.get("label") or "").strip()
    if label:
        out.add_paragraph(label)
    contact_bits = [str(basics.get(k) or "").strip() for k in ("email", "phone") if basics.get(k)]
    loc = basics.get("location") or {}
    if isinstance(loc, dict):
        loc_bits = [str(loc.get(k) or "").strip() for k in ("address", "city", "region", "postalCode", "countryCode") if loc.get(k)]
        if loc_bits:
            contact_bits.append(", ".join(loc_bits))
    elif loc:
        contact_bits.append(str(loc))
    contact_bits = [b for b in contact_bits if b]
    if contact_bits:
        out.add_paragraph(" | ".join(contact_bits))
    url = str(basics.get("url") or "").strip()
    if url:
        out.add_paragraph(url)
    for profile in basics.get("profiles") or []:
        if isinstance(profile, dict) and profile.get("url"):
            out.add_paragraph(str(profile["url"]))
    summary = str(basics.get("summary") or "").strip()
    if summary:
        out.add_heading("Summary", level=1)
        out.add_paragraph(summary)

    for entry in resume.get("work") or []:
        if not isinstance(entry, dict):
            continue
        header = " | ".join(str(entry.get(k) or "").strip() for k in ("position", "name") if entry.get(k))
        dates = " – ".join(str(entry.get(k) or "").strip() for k in ("startDate", "endDate") if entry.get(k))
        if dates:
            header = f"{header} — {dates}" if header else dates
        if header:
            para = out.add_paragraph()
            run = para.add_run(header)
            run.bold = True
        if entry.get("summary"):
            out.add_paragraph(str(entry["summary"]).strip())
        for hl in entry.get("highlights") or []:
            if str(hl).strip():
                out.add_paragraph(str(hl).strip(), style="List Bullet")

    education = resume.get("education") or []
    if education:
        out.add_heading("Education", level=1)
        for entry in education:
            if not isinstance(entry, dict):
                continue
            parts = [str(entry.get(k) or "").strip() for k in ("studyType", "area", "institution") if entry.get(k)]
            dates = " – ".join(str(entry.get(k) or "").strip() for k in ("startDate", "endDate") if entry.get(k))
            if dates:
                parts.append(dates)
            if parts:
                out.add_paragraph(", ".join(parts))

    skills = resume.get("skills") or []
    if skills:
        out.add_heading("Skills", level=1)
        tokens: list[str] = []
        for sk in skills:
            if isinstance(sk, dict):
                tokens.append(str(sk.get("name") or "").strip())
                tokens.extend(str(k).strip() for k in sk.get("keywords") or [] if str(k).strip())
            elif str(sk).strip():
                tokens.append(str(sk).strip())
        tokens = [t for t in dict.fromkeys(tokens) if t]
        if tokens:
            out.add_paragraph(", ".join(tokens))

    for section, heading in (("projects", "Projects"), ("certifications", "Certifications"),
                            ("publications", "Publications"), ("awards", "Awards"),
                            ("languages", "Languages"), ("interests", "Interests"),
                            ("references", "References")):
        items = resume.get(section) or []
        if not items:
            continue
        out.add_heading(heading, level=1)
        for item in items:
            if isinstance(item, dict):
                text = str(item.get("name") or item.get("title") or "").strip()
                if item.get("summary"):
                    text = f"{text}: {item['summary']}".strip(" :")
                if text:
                    out.add_paragraph(text, style="List Bullet")
            elif str(item).strip():
                out.add_paragraph(str(item).strip(), style="List Bullet")

    buf = io.BytesIO()
    out.save(buf)
    return buf.getvalue()


def describe_export(doc: ResumeDocument) -> dict[str, Any]:
    return {
        "sections": [h for h, items in (
            ("Summary", [doc.summary.strip()]),
            ("Work Experience", doc.experience),
            ("Education", doc.education),
            ("Skills", doc.skills),
            ("Certifications", doc.certifications),
            ("Projects", doc.projects),
        ) if any(str(x).strip() if isinstance(x, str) else True for x in items)],
        "bullets": sum(len(e.bullets) for e in doc.experience),
        "skills": len(doc.skills),
    }
