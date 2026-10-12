"""The header block (name, headline, contact) must never be reported as 'creative headings'."""

from fairhire.fitness.ats import _creative_headings, _detect_name

ALL_CAPS = """OLUFEMI OYESANYA
Backend Systems & Infrastructure Development
olufemi@example.com | +1 555 010 2030 | Lagos, Nigeria
linkedin.com/in/olufemi

Experience
Senior Backend Engineer | Acme | Jan 2020 – Present
- Built things

Skills
Python, Go, SQL
"""


def flagged(text: str) -> list[str]:
    return [line for _, line in _creative_headings(text)]


def test_all_caps_name_is_a_name_not_a_heading():
    assert _detect_name(ALL_CAPS) == "OLUFEMI OYESANYA"
    assert "OLUFEMI OYESANYA" not in flagged(ALL_CAPS)


def test_headline_under_the_name_is_not_a_heading():
    assert flagged(ALL_CAPS) == []


def test_mixed_case_and_particle_names_are_detected():
    assert _detect_name("Ciaran McDonald\nciaran@example.com\n") == "Ciaran McDonald"
    assert _detect_name("Ana de la Cruz\nana@example.com\n") == "Ana de la Cruz"
    assert _detect_name("Jean-Luc O'Neil\njl@example.com\n") == "Jean-Luc O'Neil"


def test_section_headings_are_never_taken_for_the_name():
    assert _detect_name("EXPERIENCE\nSenior Engineer | Acme | 2020 – 2022\n") is None
    assert _detect_name("RESUME\nJordan Lee\njordan@example.com\n") == "Jordan Lee"


def test_a_real_creative_heading_after_the_contact_block_is_still_flagged():
    text = ALL_CAPS.replace("Experience\n", "Career Journey\n")
    assert flagged(text) == ["Career Journey"]


def test_creative_heading_with_no_contact_block_is_still_flagged():
    text = "Jordan Lee\n\nMy Journey\nSenior Engineer | Acme | 2020 – 2022\n- Built things\n"
    assert "My Journey" in flagged(text)
