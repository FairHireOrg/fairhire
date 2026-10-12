"""File bytes -> plain text, with layout awareness for PDFs.

PDFs are read with poppler's ``-layout`` mode, which keeps horizontal structure
(right-aligned dates). If the text has a consistent gutter, the columns are
separated and re-ordered (left block, then right block), since column
interleaving is the most common way text extraction scrambles a resume.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field

ALLOWED = {".pdf", ".docx", ".txt", ".md", ".text", ".tex"}
MAX_BYTES = 10 * 1024 * 1024


@dataclass
class Extracted:
    text: str
    kind: str                       # pdf | docx | text
    notes: list[str] = field(default_factory=list)


def _pdftotext(path: str, layout: bool) -> str:
    cmd = ["pdftotext", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [path, "-"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise ValueError("This PDF could not be read. Try exporting it again or upload a DOCX.")
    return res.stdout


_DATEISH = re.compile(r"^[\w.,'’ /\-–—()]*(?:19|20)\d{2}[\w.,'’ /\-–—()]*$|^(?:Present|Current)$", re.I)


def find_gutter(layout_text: str) -> int:
    """True when text blocks sit side by side on a shared gutter.

    Right-aligned dates start at a different column on every line; a real column
    starts at the *same* column on many lines. That is what we look for.
    """
    content = [ln for ln in layout_text.splitlines() if ln.strip()]
    if len(content) < 6:
        return 0
    starts: dict[int, int] = {}
    for ln in content:
        m = re.search(r"\S( {3,})(?=\S)", ln)
        if not m:
            continue
        col = m.end()
        right = ln[col:].strip()
        if not right or _DATEISH.match(right) or len(ln[:m.start() + 1].strip()) < 3:
            continue
        starts[col] = starts.get(col, 0) + 1
    if not starts:
        return 0
    col, best = max(starts.items(), key=lambda kv: (kv[1], -kv[0]))
    return col if best >= 3 and best / len(content) >= 0.2 else 0


def looks_multicolumn(layout_text: str) -> bool:
    return find_gutter(layout_text) > 0


def split_columns(layout_text: str, gutter: int) -> str:
    """Re-order side-by-side columns into one: whole left column, then whole right.

    Lines that cross the gutter are full-width (a name banner, say) and act as
    breaks between column blocks.
    """
    out: list[str] = []
    left: list[str] = []
    right: list[str] = []

    def flush() -> None:
        nonlocal left, right
        out.extend(left)
        if left and right:
            out.append("")
        out.extend(right)
        left, right = [], []

    for ln in layout_text.splitlines():
        if not ln.strip():
            left.append("")
            if right:
                right.append("")
            continue
        crosses = len(ln) > gutter and ln[max(0, gutter - 3):gutter].strip() != ""
        if crosses:
            flush()
            out.append(ln)
        elif len(ln) > gutter and ln[gutter:].strip():
            left_part = ln[:gutter].rstrip()
            if left_part.strip():
                left.append(left_part)
            right.append(ln[gutter:].rstrip())
        else:
            left.append(ln.rstrip())
    flush()
    return "\n".join(out)


def _markdown_to_text(text: str) -> str:
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    return text


def _latex_to_text(text: str) -> str:
    """Best-effort for pasted .tex source: keep the words, drop the markup."""
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:section|subsection)\*?\{([^}]*)\}", r"\n\1\n", text)
    text = re.sub(r"\\resumeItem\{(.*)\}", r"- \1", text)
    text = re.sub(r"\\item\s+", "- ", text)
    text = re.sub(r"\\(?:textbf|textit|emph|underline|href\{[^}]*\})\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\\\|\\hfill", "   ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    return re.sub(r"[{}]", "", text)


def extract_text(data: bytes, filename: str) -> Extracted:
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > MAX_BYTES:
        raise ValueError("Resume uploads must be 10 MB or smaller.")
    suffix = os.path.splitext(filename or "")[1].lower()
    if suffix not in ALLOWED:
        raise ValueError("Unsupported file type. Upload a PDF, DOCX, TXT or Markdown file.")

    if suffix == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            layout = _pdftotext(path, layout=True)
            notes: list[str] = []
            text = layout
            gutter = find_gutter(layout)
            if gutter:
                text = split_columns(layout, gutter)
                notes.append("multi_column")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if len(re.sub(r"\s", "", text)) < 40:
            raise ValueError(
                "No selectable text was found in this PDF. It looks like a scan or an image — "
                "export it again as a text PDF, or upload a DOCX."
            )
        return Extracted(text=text, kind="pdf", notes=notes)

    if suffix == ".docx":
        from fairhire.fitness.docx_io import read_docx_text

        try:
            return Extracted(text=read_docx_text(data), kind="docx")
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ValueError("This DOCX could not be read. Re-save it from Word and try again.") from exc

    text = data.decode("utf-8", errors="replace")
    if suffix == ".md":
        text = _markdown_to_text(text)
    elif suffix == ".tex":
        text = _latex_to_text(text)
    if not text.strip():
        raise ValueError("The uploaded file is empty.")
    return Extracted(text=text, kind="text")
