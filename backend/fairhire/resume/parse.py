"""Rule-based resume parser: text (any layout) -> canonical ``Resume``.

Pure function of its input: no model, no randomness, no I/O. The same text
always yields the same document, byte for byte.

Pipeline
  1. normalize   unicode, ligatures, private-use bullet glyphs, tabs
  2. classify    every line: blank / heading / bullet / continuation / header
  3. segment     split into sections, then entries inside each section
  4. interpret   entry header fragments -> heading, subheading, dates, ...

Nothing is discarded: lines that match no rule are kept as the heading or a
bullet of the closest entry, or end up in ``contact.other``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from fairhire.fitness.lexicon import section_aliases
from fairhire.resume.model import DEFAULT_TITLES, Contact, Entry, Resume, Section, SkillGroup

# ---------------------------------------------------------------- patterns

_MON = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Spring|Summer|Fall|Autumn|Winter)\.?"
)
_YEAR = r"(?:19|20)\d{2}"
_POINT = rf"(?:(?:{_MON}[ \t]*)?{_YEAR}|\d{{1,2}}/{_YEAR}|Present|Current|Now|Ongoing|Today)"
_PREFIX = r"(?:(?:Expected|Anticipated|Graduat(?:ed|ion|ing)|Class of|Since)[ \t:]*)?"
RANGE_RE = re.compile(rf"{_PREFIX}\b{_POINT}[ \t]*(?:[-–—]|to)[ \t]*{_POINT}\b", re.I)
SINGLE_RE = re.compile(rf"{_PREFIX}\b(?:{_MON}[ \t]*)?{_YEAR}\b", re.I)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\d/])(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s|,;<>()]+|"
    r"(?:linkedin\.com|github\.com|gitlab\.com|bitbucket\.org|behance\.net|dribbble\.com|medium\.com)/[^\s|,;<>()]+|"
    r"\b[\w\-]+(?:\.[\w\-]+)*\.(?:com|org|net|io|dev|me|co|ai|app|tech|xyz)(?:/[^\s|,;<>()]*)?",
    re.I,
)

_BULLET_GLYPHS = "-*•·▪■□◦‣►▸▶➢➤✓✔→–—○●◆◇➔"
BULLET_RE = re.compile(rf"^(\s*)([{re.escape(_BULLET_GLYPHS)}]|\d{{1,2}}[.)])\s+(?=\S)")

_ORG_RE = re.compile(
    r"\b(?:Inc|LLC|Ltd|Corp|Corporation|Co|Company|GmbH|PLC|University|College|Institute|School|Academy|"
    r"Labs?|Laboratory|Technologies|Systems|Solutions|Group|Foundation|Bank|Hospital|Studio|Studios|"
    r"Software|Consulting|Partners|Agency|Association|Society|Department|Services|Ventures|Network|"
    r"Center|Centre|Lab|Council|Club|Team|Press|Airlines|Motors|Health|Media)\b\.?",
    re.I,
)
_ROLE_RE = re.compile(
    r"\b(?:engineer|developer|manager|analyst|designer|scientist|intern|internship|instructor|trainer|"
    r"architect|consultant|founder|co-?founder|lead|researcher|research|director|specialist|"
    r"administrator|coordinator|associate|assistant|officer|president|vice|chair|head|teacher|tutor|"
    r"technician|programmer|writer|editor|fellow|volunteer|captain|mentor|ta|tutor|supervisor|"
    r"representative|advisor|adviser|partner|owner|operator|clerk|cashier|barista|server|"
    r"freelance|contractor|apprentice|resident|professor|lecturer|chief|ceo|cto|cfo|coo|vp|swe|sde|"
    r"dev|devops|sre|qa|tester|strategist|planner|producer|accountant|auditor|nurse|therapist)\b",
    re.I,
)
_DEGREE_ABBR_RE = re.compile(   # case-sensitive: "MA" the degree, not "ma"
    r"\b(?:B\.?\s?S\.?|B\.?\s?A\.?|B\.?\s?Eng\.?|B\.?\s?Tech\.?|M\.?\s?S\.?|M\.?\s?A\.?|M\.?\s?Eng\.?|"
    r"M\.?\s?Tech\.?|M\.?\s?B\.?\s?A\.?|Ph\.?\s?D\.?|B\.?Sc\.?|M\.?Sc\.?|A\.?A\.?S?\.?|B\.?F\.?A\.?|"
    r"M\.?F\.?A\.?|B\.?B\.?A\.?|LL\.?B\.?|LL\.?M\.?|J\.?D\.?|M\.?D\.?|M\.?Ed\.?|B\.?Com\.?|BSc|MSc)(?=[\s,.)]|$)"
)
_DEGREE_RE = re.compile(
    r"\b(?:Bachelors?(?:'s|’s)?|Masters?(?:'s|’s)?|Doctorate|Doctor|Associates?(?:'s|’s)?|Diploma|Certificate|"
    r"High School|GED|Minor|Major)\b",
    re.I,
)
_US_STATE = r"(?:A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])"
_US_STATE_NAMES = (
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|"
    "Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|"
    "Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
    "North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|"
    "Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|Ontario|Quebec|British Columbia|Alberta"
)
_COUNTRIES = (
    "USA|US|U\\.S\\.|United States|UK|United Kingdom|England|Scotland|Canada|India|Germany|France|Spain|Italy|"
    "Netherlands|Ireland|Ghana|Nigeria|Kenya|South Africa|Egypt|Brazil|Mexico|Argentina|Colombia|Chile|China|Japan|"
    "South Korea|Singapore|Australia|New Zealand|Israel|UAE|Pakistan|Bangladesh|Sweden|Norway|Denmark|Finland|"
    "Poland|Portugal|Switzerland|Austria|Belgium|Turkey|Philippines|Vietnam|Indonesia|Thailand|Malaysia"
)
_PLACE = rf"(?:{_US_STATE}|{_US_STATE_NAMES}|{_COUNTRIES})"
_LOCATION_RE = re.compile(
    rf"^(?:[A-Z][\w.'’\-]+(?: [A-Z][\w.'’\-]+){{0,3}}),\s*{_PLACE}(?:,\s*{_PLACE})?$"
    r"|^(?:Remote|Hybrid|On-?site|Worldwide)(?:\s*[,/(].*)?$",
)
_EDU_EXTRA_RE = re.compile(
    r"^(?:GPA|G\.P\.A|CGPA|Cumulative|Honou?rs?|Dean|Magna|Summa|Cum Laude|Minor|Concentration|"
    r"Coursework|Relevant|Courses|Thesis|Capstone|Advisor|Awards?|Activities|Major)\b",
    re.I,
)

# heading text -> kind. Aliases from the shared lexicon plus common extras.
_EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("about me", "about", "who i am", "hello", "professional summary", "summary of qualifications", "personal statement", "professional statement", "career statement", "statement", "personal profile", "personal summary", "overview", "profile summary", "career summary"),
    "experience": ("where i've worked", "where i have worked", "what i've done", "work experience & leadership", "relevant experience", "professional background", "work", "employment experience", "internships", "industry experience", "research experience", "teaching experience", "leadership experience", "volunteer experience", "leadership", "volunteering", "volunteer work", "military service", "experience and leadership"),
    "education": ("school", "schooling", "academic background", "education and training", "academic history", "education & certifications", "educational background"),
    "skills": ("what i know", "what i can do", "toolbox", "technical proficiencies", "skills & tools", "skills and tools", "areas of expertise", "expertise", "technical expertise", "languages", "languages and tools", "programming languages", "interests", "hobbies", "hobbies & interests", "interests & hobbies", "skills & interests", "additional information", "other skills"),
    "projects": ("personal projects", "academic projects", "side projects", "selected projects", "open source", "open source contributions", "portfolio", "key projects", "research projects"),
    "publications": ("papers", "research", "publications and talks", "selected publications", "talks", "presentations", "patents"),
    "certifications": ("licenses", "licenses & certifications", "licenses and certifications", "certificates", "certification", "training", "professional development", "courses"),
    "awards": ("awards", "award", "honors", "honours", "honors & awards", "honors and awards", "awards & honors", "achievements", "accomplishments", "scholarships", "recognition", "extracurricular activities", "extracurriculars", "activities", "clubs"),
}
_SECTION_KIND = {
    "summary": "summary", "experience": "experience", "education": "education", "skills": "skills",
    "projects": "projects", "publications": "publications", "certifications": "certifications",
    "awards": "awards", "references": "references",
}


def _heading_table() -> dict[str, str]:
    table: dict[str, str] = {}
    for key, aliases in section_aliases().items():
        kind = _SECTION_KIND.get(key)
        if kind is None:
            continue
        for alias in aliases:
            table[alias] = kind
        table[key] = kind
    for key, aliases in _EXTRA_ALIASES.items():
        for alias in aliases:
            table.setdefault(alias, key)
    table.setdefault("references", "references")
    table.setdefault("contact", "contact")
    return table


_HEADINGS = _heading_table()


def _norm_heading(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z&\s]", " ", line)).strip().lower()


# ---------------------------------------------------------------- normalize

_PRIVATE_BULLETS = dict.fromkeys(map(ord, ""), "•")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.translate(_PRIVATE_BULLETS)
    text = re.sub(r"[­​‌‍﻿]", "", text)
    text = re.sub(r"[  -   　]", " ", text)
    text = text.replace("\f", "\n\n")
    text = text.replace("\t", "    ")
    # Re-join words broken across lines by hyphenation ("develop-\nment").
    text = re.sub(r"(?<=[a-z])-\n\s*(?=[a-z])", "", text)
    return "\n".join(line.rstrip() for line in text.split("\n"))


# ---------------------------------------------------------------- line model


@dataclass
class Line:
    raw: str
    text: str            # stripped, bullet marker removed
    indent: int          # column of first glyph (marker included)
    text_indent: int     # column where the text itself starts
    bullet: bool
    blank: bool
    n: int

    @property
    def parts(self) -> list[str]:
        """Split on layout gaps: ``Title      May 2023 - Present`` -> two parts."""
        return [p.strip() for p in re.split(r" {3,}", self.text) if p.strip()]


def _make_line(raw: str, n: int) -> Line:
    if not raw.strip():
        return Line(raw, "", 0, 0, False, True, n)
    m = BULLET_RE.match(raw)
    if m:
        marker = m.group(2)
        # "2023 - 2024" or "2 years of..." are not list markers.
        is_number = marker[:1].isdigit()
        looks_like_date = is_number and re.match(r"^\s*\d{1,2}[.)]\s+(?:19|20)\d{2}", raw)
        dash_range = marker in "-–—" and re.match(rf"^\s*[-–—]\s+{_POINT}", raw, re.I) and False
        if not looks_like_date and not dash_range:
            return Line(raw, raw[m.end():].strip(), len(m.group(1)), m.end(), True, False, n)
    stripped = raw.lstrip()
    indent = len(raw) - len(stripped)
    return Line(raw, stripped.strip(), indent, indent, False, False, n)


def _is_date_only(text: str) -> bool:
    t = RANGE_RE.sub("", text, count=1) if RANGE_RE.search(text) else SINGLE_RE.sub("", text, count=1)
    return not re.sub(r"[\s,|·•()\-–—]", "", t)


def _has_date(text: str) -> bool:
    return bool(RANGE_RE.search(text) or SINGLE_RE.search(text))


def heading_kind(line: Line, caps_style: bool) -> str | None:
    """Return the section kind if ``line`` is a heading, else None."""
    if line.blank or line.bullet:
        return None
    text = line.text.strip().rstrip(":").strip()
    if not text or len(text) > 48 or len(text.split()) > 6 or _has_date(text) or EMAIL_RE.search(text):
        return None
    if re.search(r" {3,}", line.text):
        return None
    norm = _norm_heading(text)
    if norm in _HEADINGS:
        # "Languages" / "Research" can be a role fragment; require heading-like form.
        letters = re.sub(r"[^A-Za-z]", "", text)
        upper = sum(c.isupper() for c in letters) / max(len(letters), 1)
        if upper >= 0.7 or text.istitle() or text.islower() or line.text.rstrip().endswith(":") or text.lower() in _HEADINGS:
            return _HEADINGS[norm]
    letters = re.sub(r"[^A-Za-z]", "", text)
    if caps_style and len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) >= 0.95 and len(text.split()) <= 4:
        return "custom"
    return None


# ---------------------------------------------------------------- fragments

_FRAG_SPLIT_RE = re.compile(r"\s*\|\s*|\s+[·•]\s+|\s+[–—]\s+|\s+-\s+|\s+@\s+|\s*/{2}\s*")
_STATE_ONLY_RE = re.compile(rf"^{_PLACE}$")


def _comma_pieces(text: str) -> list[str]:
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    merged: list[str] = []
    for piece in out:
        if not piece:
            continue
        if merged and _STATE_ONLY_RE.match(piece):
            merged[-1] = f"{merged[-1]}, {piece}"
        else:
            merged.append(piece)
    return merged


def is_location(frag: str) -> bool:
    return bool(_LOCATION_RE.match(frag.strip()))


def is_org(frag: str) -> bool:
    return bool(_ORG_RE.search(frag))


def is_role(frag: str) -> bool:
    return bool(_ROLE_RE.search(frag))


def is_degree(frag: str) -> bool:
    return bool(_DEGREE_ABBR_RE.search(frag) or _DEGREE_RE.search(frag))


@dataclass
class Header:
    frags: list[str]
    start: str = ""
    end: str = ""
    location: str = ""
    link: str = ""
    extras: list[str] | None = None


def _split_dates(text: str) -> tuple[str, str, str]:
    m = RANGE_RE.search(text)
    if m:
        body = re.sub(rf"^{_PREFIX}", "", m.group(0), flags=re.I)
        a, b = re.split(r"\s*(?:[-–—]|\bto\b)\s*", body, maxsplit=1, flags=re.I)
        a, b = a.strip(), b.strip()
        if re.match(r"^(?:expected|anticipated)", m.group(0), re.I):
            a = re.sub(r"^(?:Expected|Anticipated)\s*", "", a, flags=re.I)
        return a, b, (text[: m.start()] + " | " + text[m.end():]).strip(" |,–—-·•")
    m = SINGLE_RE.search(text)
    if m:
        return "", re.sub(r"^\s*(?:Graduated|Since)\s*", "", m.group(0), flags=re.I).strip(), (text[: m.start()] + " | " + text[m.end():]).strip(" |,–—-·•")
    return "", "", text


def read_header(lines: list[Line], kind: str) -> Header:
    """Turn the header lines of one entry into ordered fragments + fields."""
    h = Header(frags=[], extras=[])
    for ln in lines:
        for part in ln.parts:
            text = part
            link = URL_RE.search(text)
            if link and not EMAIL_RE.search(text) and not h.link:
                h.link = link.group(0).rstrip(".,;")
                text = (text[: link.start()] + " | " + text[link.end():]).strip(" |·•-–—,")
            if not h.start and not h.end and _has_date(text):
                s, e, text = _split_dates(text)
                h.start, h.end = s, e
            pieces = [p.strip(" ·•|,–—") for p in _FRAG_SPLIT_RE.split(text) if p.strip(" ·•|,–—")]
            expanded: list[str] = []
            for piece in pieces:
                if ", " in piece and not is_location(piece):
                    sub = _comma_pieces(piece)
                    if len(sub) > 1 and (kind in ("education", "experience") or all(len(s.split()) <= 6 for s in sub)):
                        expanded.extend(sub)
                        continue
                expanded.append(piece)
            for piece in expanded:
                if is_location(piece) and not h.location:
                    h.location = piece
                else:
                    h.frags.append(piece)
    return h


def interpret(h: Header, kind: str) -> Entry:
    e = Entry(start=h.start, end=h.end, location=h.location, link=h.link)
    frags = list(h.frags)
    if kind == "education":
        degree = next((f for f in frags if is_degree(f) and not is_org(f)), None) or next((f for f in frags if is_degree(f)), None)
        if degree:
            frags.remove(degree)
        school = next((f for f in frags if is_org(f)), None)
        if school:
            frags.remove(school)
        extras = [f for f in frags if _EDU_EXTRA_RE.match(f)]
        rest = [f for f in frags if f not in extras]
        if not school and rest:
            school = rest.pop(0)
        if not degree and rest and not _EDU_EXTRA_RE.match(rest[0]):
            degree = rest.pop(0)
        if not degree and school and not rest:
            degree, school = school, ""
        # A degree line often carries its field: "B.S., Computer Science".
        if degree and rest and not _EDU_EXTRA_RE.match(rest[0]) and len(rest[0].split()) <= 6 and not is_org(rest[0]):
            degree = f"{degree}, {rest.pop(0)}"
        e.heading, e.subheading = degree or "", school or ""
        e.detail = "; ".join(extras + rest)
    elif kind == "experience":
        role = next((f for f in frags if is_role(f) and not (is_org(f) and not _ROLE_RE.search(f.split()[0]))), None) or next((f for f in frags if is_role(f)), None)
        if role is None and frags:
            role = frags[0]
        if role in frags:
            frags.remove(role)
        org = next((f for f in frags if is_org(f)), None) or (frags[0] if frags else None)
        if org in frags:
            frags.remove(org)
        e.heading, e.subheading = role or "", org or ""
        e.detail = "; ".join(frags)
    elif kind == "projects":
        if frags:
            e.heading = frags[0]
            e.detail = ", ".join(frags[1:])
    else:
        if frags:
            e.heading = frags[0]
            if len(frags) > 1:
                e.subheading = frags[1]
            if len(frags) > 2:
                e.detail = "; ".join(frags[2:])
    return e


# ---------------------------------------------------------------- segment


def _is_continuation(prev: Line, ln: Line, in_bullet: bool) -> bool:
    """Is ``ln`` the wrapped tail of the previous bullet / paragraph line?"""
    if ln.blank or ln.bullet or not in_bullet:
        return False
    if _has_date(ln.text) and (len(ln.text.split()) <= 10 or not re.search(r"[.!?]$", ln.text)):
        return False
    if " | " in ln.text:
        return False
    if len(ln.parts) > 1:
        return False
    if ln.indent >= prev.text_indent and prev.text_indent > 0:
        return True
    if ln.text[:1].islower() or ln.text[:1] in ",;)":
        return True
    # Flush-left wrap (non-layout extraction): the previous line ran long and did not
    # close a sentence, and this line does not look like a short title/company header.
    header_like = len(ln.text.split()) <= 5 and ln.text[:1].isupper()
    return len(prev.text) >= 60 and not re.search(r"[.!?:]$", prev.text) and not header_like


def _header_complete(lines: list[Line], kind: str) -> bool:
    """A header is complete once it spans two lines or names two things."""
    if len(lines) >= 2:
        return True
    return bool(lines) and len(read_header(lines, kind).frags) >= 2


def _split_skill_items(text: str) -> list[str]:
    items: list[str] = []
    depth = 0
    cur = ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch in ",;|•·" and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    items.append(cur.strip())
    return [i for i in (re.sub(r"\s+", " ", i).strip(" .") for i in items) if i]


_LABEL_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 &/+#.\-]{1,40}?)\s*:\s*(.*)$")


def parse_skills(lines: list[Line]) -> list[SkillGroup]:
    groups: list[SkillGroup] = []
    cur: SkillGroup | None = None
    carry = False
    for ln in lines:
        if ln.blank:
            carry = False
            continue
        text = ln.text
        m = _LABEL_RE.match(text) if not URL_RE.match(text) else None
        if m and len(m.group(1).split()) <= 5:
            cur = SkillGroup(label=m.group(1).strip(), items=_split_skill_items(m.group(2)))
            groups.append(cur)
            carry = text.rstrip().endswith(",")
        elif cur is not None and (carry or ln.indent > 0 and not ln.bullet and cur.items):
            cur.items.extend(_split_skill_items(text))
            carry = text.rstrip().endswith(",")
        else:
            items = _split_skill_items(text)
            if cur is not None and cur.label == "" and not ln.blank:
                cur.items.extend(items)
            else:
                cur = SkillGroup(label="", items=items)
                groups.append(cur)
            carry = text.rstrip().endswith(",")
    return [g for g in groups if g.items or g.label]


def parse_entries(lines: list[Line], kind: str, id_prefix: str) -> list[Entry]:
    flat = kind in ("certifications", "awards")
    entries: list[Entry] = []
    header: list[Line] = []
    bullets: list[list[str]] = []   # parallel: bullet texts per open entry
    cur: Entry | None = None
    cur_bullets: list[str] = []
    prev: Line | None = None
    in_bullet = False

    def close() -> None:
        nonlocal cur, header, cur_bullets
        if header or cur_bullets:
            e = interpret(read_header(header, kind), kind) if header else Entry()
            e.bullets = cur_bullets
            if not e.heading and not e.subheading and cur_bullets and not header:
                pass
            entries.append(e)
        header, cur_bullets, cur = [], [], None

    for ln in lines:
        if ln.blank:
            prev, in_bullet = ln, False
            # A blank line ends bullet wrapping but not the entry.
            continue
        if prev is not None and not prev.blank and _is_continuation(prev, ln, in_bullet):
            if cur_bullets:
                cur_bullets[-1] = f"{cur_bullets[-1]} {ln.text}".strip()
            elif header:
                header[-1] = Line(header[-1].raw, f"{header[-1].text} {ln.text}", header[-1].indent, header[-1].text_indent, False, False, header[-1].n)
            prev = ln
            continue
        if ln.bullet:
            if flat:
                # certification / award bullets are items of their own
                close()
                header = [Line(ln.raw, ln.text, ln.indent, ln.text_indent, False, False, ln.n)]
                close()
            else:
                cur_bullets.append(ln.text)
            prev, in_bullet = ln, True
            continue
        # Plain text line.
        if kind == "education" and (header or cur_bullets) and _EDU_EXTRA_RE.match(ln.text):
            header.append(ln)
            prev, in_bullet = ln, False
            continue
        if flat:
            close()
            header = [ln]
            close()
            prev, in_bullet = ln, False
            continue
        if header and not cur_bullets and _is_date_only(ln.text) and not (lambda h: h.start or h.end)(read_header(header, kind)):
            header.append(ln)
            prev, in_bullet = ln, False
            continue
        long_prose = (len(ln.text.split()) >= 8 or ln.text.endswith(".")) and " | " not in ln.text and not RANGE_RE.search(ln.text)
        if header and not cur_bullets and _header_complete(header, kind) and long_prose and len(ln.parts) == 1:
            cur_bullets.append(ln.text)
            prev, in_bullet = ln, True
            continue
        starts_new = False
        if cur_bullets and long_prose and len(ln.parts) == 1 and not _has_date(ln.text):
            cur_bullets.append(ln.text)   # unmarked prose line under the same entry
            prev, in_bullet = ln, True
            continue
        if cur_bullets:
            starts_new = True
        elif header and _header_complete(header, kind):
            starts_new = True
        if starts_new:
            close()
        header.append(ln)
        prev, in_bullet = ln, False
    close()
    out: list[Entry] = []
    for i, e in enumerate(entries):
        e.id = f"{id_prefix}-e{i}"
        if not e.is_empty():
            out.append(e)
    return out


# ---------------------------------------------------------------- contact


def _is_plain_headline(text: str) -> bool:
    """A short label under the name: not a sentence, no digits, no contact data."""
    words = text.split()
    return 1 <= len(words) <= 10 and not re.search(r"[.!?]$", text.strip()) and not any(ch.isdigit() for ch in text)


def parse_contact(lines: list[Line]) -> tuple[Contact, str]:
    """Header block above the first section heading. Returns (contact, loose_prose)."""
    c = Contact()
    prose: list[str] = []
    after_name = False  # True only for the very next line after the name
    for ln in lines:
        if ln.blank:
            continue
        text = ln.text
        directly_after_name, after_name = after_name, False
        email = EMAIL_RE.search(text)
        phone = PHONE_RE.search(text)
        urls = [u.group(0) for u in URL_RE.finditer(EMAIL_RE.sub(" ", text))]
        fragments = [f.strip(" ·•▪■◦●◆|,;") for f in re.split(r"\s*[|·•▪■◦●◆]\s*|\s{3,}|\s+[–—]\s+", text) if f.strip(" ·•▪■◦●◆|,;")]
        if not (email or phone or urls) and not c.name and 1 <= len(text.split()) <= 5 and not any(ch.isdigit() for ch in text) and not is_location(text):
            c.name = text.strip()
            after_name = True
            continue
        if email or phone or urls:
            for frag in fragments:
                if EMAIL_RE.search(frag):
                    c.email = c.email or EMAIL_RE.search(frag).group(0)
                    rest = EMAIL_RE.sub("", frag).strip(" ·•|,;:")
                    if rest and not re.fullmatch(r"(?i)e-?mail|email", rest) and rest not in c.other:
                        c.other.append(rest)
                elif PHONE_RE.search(frag):
                    c.phone = c.phone or PHONE_RE.search(frag).group(0).strip()
                elif URL_RE.search(frag):
                    for u in URL_RE.finditer(frag):
                        url = u.group(0).rstrip(".,;")
                        if url not in c.links:
                            c.links.append(url)
                elif is_location(frag) or (not c.location and len(frag.split()) <= 5 and not is_role(frag)):
                    c.location = c.location or frag
                elif frag not in c.other:
                    c.other.append(frag)
            continue
        if is_location(text) and not c.location:
            c.location = text
        elif is_role(text) and len(text.split()) <= 10 and not c.headline and c.name:
            c.headline = text
        elif directly_after_name and not c.headline and _is_plain_headline(text):
            # "Backend Systems & Infrastructure Development": a title line with no job-title word in it.
            c.headline = text.strip()
        elif len(text.split()) >= 10:
            prose.append(text)
        elif c.name and text not in c.other:
            c.other.append(text)
        elif not c.name:
            c.name = text
    return c, " ".join(prose)


# ---------------------------------------------------------------- top level


def parse_resume_text(text: str) -> Resume:
    lines = [_make_line(raw, i) for i, raw in enumerate(normalize_text(text).split("\n"))]
    # Style detection: if known headings are ALL CAPS, unknown ALL CAPS lines are headings too.
    known = [ln for ln in lines if not ln.blank and not ln.bullet and heading_kind(ln, False) not in (None, "custom")]
    caps = sum(1 for ln in known if ln.text.upper() == ln.text and re.search(r"[A-Z]", ln.text))
    caps_style = (not known) or caps / len(known) >= 0.5

    blocks: list[tuple[str, str, list[Line]]] = []   # (kind, title as written, lines)
    head: list[Line] = []
    current: tuple[str, str, list[Line]] | None = None
    for ln in lines:
        kind = heading_kind(ln, caps_style)
        # An unknown caps line must follow a blank line or the top of the file.
        if kind == "custom":
            idx = ln.n
            before_blank = idx == 0 or lines[idx - 1].blank
            if not before_blank or current is None and not head:
                kind = None
        if kind is not None:
            current = (kind, ln.text.strip().rstrip(":").strip(), [])
            blocks.append(current)
        elif current is None:
            head.append(ln)
        else:
            current[2].append(ln)

    contact, prose = parse_contact(head)
    summary = prose
    sections: list[Section] = []
    for kind, title, body in blocks:
        body = _trim(body)
        if not body:
            continue
        if kind == "contact":
            extra, more_prose = parse_contact(body)
            for f in ("name", "headline", "email", "phone", "location"):
                if not getattr(contact, f):
                    setattr(contact, f, getattr(extra, f))
            contact.links += [u for u in extra.links if u not in contact.links]
            contact.other += [o for o in extra.other if o not in contact.other]
            continue
        if kind == "summary":
            para = " ".join(re.sub(r"\s+", " ", b.text) for b in body if not b.blank)
            summary = f"{summary} {para}".strip() if summary else para
            continue
        if kind == "references":
            sections.append(_custom_text(f"s{len(sections)}", title, body))
            continue
        sid = f"s{len(sections)}"
        sec = Section(id=sid, kind=kind if kind != "custom" else "custom", title=title)
        if kind == "skills":
            sec.groups = parse_skills(body)
            if not sec.groups:
                continue
        else:
            sec.entries = parse_entries(body, kind, sid)
            if not sec.entries:
                continue
            if kind == "custom":
                sec.kind = _infer_kind(sec.entries)
        sections.append(sec)
    # Contact fallback: nothing recognized above the first heading -> take it from the full text.
    if not contact.email:
        m = EMAIL_RE.search(text)
        if m:
            contact.email = m.group(0)
    return Resume(contact=contact, summary=summary, sections=sections)


def _infer_kind(entries: list[Entry]) -> str:
    """Creative headings: classify the section by what its entries look like."""
    n = len(entries)
    dated_roles = sum(1 for e in entries if (e.start or e.end) and is_role(e.heading))
    schooled = sum(1 for e in entries if is_degree(e.heading) or is_degree(e.subheading) or re.search(r"\b(?:university|college|school|institute)\b", f"{e.heading} {e.subheading}", re.I))
    if dated_roles * 2 >= n:
        return "experience"
    if schooled * 2 >= n:
        return "education"
    return "custom"


def _custom_text(sid: str, title: str, body: list[Line]) -> Section:
    sec = Section(id=sid, kind="custom", title=title)
    sec.entries = parse_entries(body, "custom", sid)
    return sec


def _trim(lines: list[Line]) -> list[Line]:
    while lines and lines[0].blank:
        lines = lines[1:]
    while lines and lines[-1].blank:
        lines = lines[:-1]
    return lines


__all__ = ["parse_resume_text", "normalize_text", "DEFAULT_TITLES"]
