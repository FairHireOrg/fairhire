"""ATS-safe exporters: .docx and .txt from a ``Resume``.

Single column, no tables, no text boxes, no images, real heading styles and
real list paragraphs, so every parser reads the same order a human does.
"""

from __future__ import annotations

import io

from fairhire.resume.model import Resume
from fairhire.resume.render import contact_lines, header_line, render_text, section_title


def export_txt(r: Resume) -> bytes:
    return render_text(r).encode("utf-8")


def export_docx(r: Resume) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    for section in doc.sections:
        section.left_margin = section.right_margin = Pt(54)
        section.top_margin = section.bottom_margin = Pt(50)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(2)

    lines = contact_lines(r)
    if lines:
        title = doc.add_heading(lines[0], level=0)
        for run in title.runs:
            run.font.size = Pt(20)
        for text in lines[1:]:
            doc.add_paragraph(text)
    if r.summary.strip():
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(r.summary.strip())
    for sec in r.sections:
        has_body = bool(sec.groups) if sec.kind == "skills" else bool(sec.entries)
        if not has_body:
            continue
        doc.add_heading(section_title(sec), level=1)
        if sec.kind == "skills":
            for g in sec.groups:
                items = ", ".join(i for i in g.items if i)
                p = doc.add_paragraph()
                if g.label:
                    p.add_run(f"{g.label}: ").bold = True
                p.add_run(items)
            continue
        for e in sec.entries:
            head = header_line(e)
            if head:
                doc.add_paragraph().add_run(head).bold = True
            for b in e.bullets:
                if b.strip():
                    doc.add_paragraph(b.strip(), style="List Bullet")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
