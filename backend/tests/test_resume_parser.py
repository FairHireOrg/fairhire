"""Parser contract: deterministic, lossless, stable under re-render."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from fairhire.resume import parse_resume_text, render_text
from fairhire.resume.parse import _HEADINGS, normalize_text

FIXTURES = Path(__file__).parent / "fixtures"
TEXTS = sorted(FIXTURES.glob("*.txt"))


def _ids_stripped(d):
    """Ids are bookkeeping and headings are standardised on render, so neither is compared."""
    if isinstance(d, dict):
        return {k: _ids_stripped(v) for k, v in d.items() if k not in ("id", "title")}
    if isinstance(d, list):
        return [_ids_stripped(v) for v in d]
    return d


def _words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9+#.\-/]{2,}", normalize_text(text))}


@pytest.mark.parametrize("path", TEXTS, ids=lambda p: p.stem)
def test_deterministic(path):
    text = path.read_text()
    assert parse_resume_text(text).to_dict() == parse_resume_text(text).to_dict()


@pytest.mark.parametrize("path", TEXTS, ids=lambda p: p.stem)
def test_nothing_is_dropped(path):
    """Every word of the input survives somewhere in the parsed document."""
    text = path.read_text()
    parsed = parse_resume_text(text)
    out = _words(render_text(parsed))
    # Section headings are standardised on render ("Professional Experience" -> "Work
    # Experience") and that is intentional; everything else must survive.
    headings = set().union(*(_words(h) for h in _HEADINGS)) | set().union(*(_words(s.title) for s in parsed.sections))
    missing = {w for w in _words(text) - out - headings if not re.fullmatch(r"[\d\-.]+", w)}
    assert not missing, f"dropped: {sorted(missing)}"


@pytest.mark.parametrize("path", TEXTS, ids=lambda p: p.stem)
def test_render_roundtrip_is_stable(path):
    """parse(render(parse(x))) == parse(x): an ATS reading our export recovers the same document."""
    first = parse_resume_text(path.read_text())
    second = parse_resume_text(render_text(first))
    assert _ids_stripped(second.to_dict()) == _ids_stripped(first.to_dict())


def test_pdf_fixture_if_present():
    pdf = FIXTURES / "sample.pdf"
    if not pdf.exists():
        pytest.skip("no sample.pdf fixture")
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    r = parse_resume_text(text)
    assert r.contact.email and r.sections


def test_latex_style_entries():
    r = parse_resume_text((FIXTURES / "latex_jake.txt").read_text())
    exp = next(s for s in r.sections if s.kind == "experience")
    assert [(e.heading, e.subheading, e.location) for e in exp.entries] == [
        ("Software Engineer", "Stripe", "San Francisco, CA"),
        ("Software Engineering Intern", "Google", "Mountain View, CA"),
    ]
    assert exp.entries[0].start == "June 2024" and exp.entries[0].end == "Present"
    edu = next(s for s in r.sections if s.kind == "education")
    assert edu.entries[0].subheading == "Stanford University" and edu.entries[0].detail == "GPA: 3.9/4.0"
    assert r.contact.phone == "(555) 123-4567" and len(r.contact.links) == 2


def test_wrapped_bullets_are_rejoined():
    r = parse_resume_text((FIXTURES / "raw_wrapped.txt").read_text())
    exp = next(s for s in r.sections if s.kind == "experience")
    assert exp.entries[0].bullets[0].endswith("across four regions")
    assert len(exp.entries[0].bullets) == 2


def test_creative_headings_are_classified():
    r = parse_resume_text((FIXTURES / "creative.txt").read_text())
    kinds = [s.kind for s in r.sections]
    assert kinds == ["experience", "skills", "education"]
    assert r.summary == "Designer who ships."


def test_two_column_pdf_is_untangled():
    from fairhire.resume.extract import extract_text
    pdf = FIXTURES / "two_column.pdf"
    ex = extract_text(pdf.read_bytes(), "two_column.pdf")
    assert "multi_column" in ex.notes
    r = parse_resume_text(ex.text)
    exp = next(s for s in r.sections if s.kind == "experience")
    assert [e.heading for e in exp.entries] == ["Software Engineer", "Developer"]
    assert exp.entries[0].bullets[0].endswith("2M customers")
    assert r.contact.phone == "555-123-4567" and r.contact.location == "Austin, TX"


STATEMENT_RESUME = """OLUFEMI OYESANYA
Backend Systems & Infrastructure Development
olufemi.oyesanya@example.com | +234 801 234 5678 | Lagos, Nigeria
linkedin.com/in/olufemi

PROFESSIONAL STATEMENT
Backend engineer building reliable distributed systems.

Experience
Senior Backend Engineer | Acme Corp | Jan 2020 – Present
- Built event-driven services handling 2M requests per day

Skills
Languages: Python, Go, SQL
"""


def test_all_caps_name_and_plain_headline_are_the_header():
    r = parse_resume_text(STATEMENT_RESUME)
    assert r.contact.name == "OLUFEMI OYESANYA"
    assert r.contact.headline == "Backend Systems & Infrastructure Development"
    assert r.contact.other == []


def test_statement_headings_open_the_summary():
    r = parse_resume_text(STATEMENT_RESUME)
    assert r.summary == "Backend engineer building reliable distributed systems."


def test_line_after_the_name_that_is_a_sentence_is_not_a_headline():
    r = parse_resume_text("Jordan Lee\nI build backend systems for small teams.\njordan@example.com\n\nSkills\nPython, Go\n")
    assert r.contact.headline == ""
