import json
import random
import re
import uuid
from typing import Any

import pandas as pd

from fairhire.config import Config
from fairhire.stage1.name_pools import (
    NAME_POOLS,
    RACE_CODING,
    GENDER_CODING,
    PRONOUNS,
)

GENDERED_TERMS = [
    (r"\bchairman\b", "chairperson"),
    (r"\bchairwoman\b", "chairperson"),
    (r"\bwaitress\b", "server"),
    (r"\bstewardess\b", "flight attendant"),
    (r"\bsalesman\b", "salesperson"),
    (r"\bsaleswoman\b", "salesperson"),
    (r"\bpoliceman\b", "police officer"),
    (r"\bpolicewoman\b", "police officer"),
    (r"\bfireman\b", "firefighter"),
    (r"\bfirewoman\b", "firefighter"),
    (r"\bmailman\b", "mail carrier"),
    (r"\bcraftsman\b", "craftsperson"),
    (r"\bhandyman\b", "handyperson"),
    (r"\bombudsman\b", "ombudsperson"),
    (r"\bforeman\b", "foreperson"),
    (r"\bbusinessman\b", "businessperson"),
    (r"\bbusinesswoman\b", "businessperson"),
    (r"\bspokesman\b", "spokesperson"),
    (r"\bspokeswoman\b", "spokesperson"),
    (r"\bmanpower\b", "workforce"),
    (r"\bman-made\b", "artificial"),
    (r"\bman hours?\b", "person hours"),
    (r"\bworkmanship\b", "work quality"),
    (r"\bgirl friday\b", "assistant"),
    (r"\bman (?!aged|ifest|ipulat|ner|uscript|ufact|datory|ual|euver|date|agement|ager|darin|neris|ifesto|ipulate|uscript\b)", ""),
    (r"\bwoman\b", "person"),
]

IDENTITY_AFFILIATIONS = [
    (r"Society of Women Engineers", "Engineering Professional Society"),
    (r"Women in Tech(?:nology)?", "Tech Professionals Association"),
    (r"Black Engineers (?:Society|Association)", "Engineering Society"),
    (r"(?:National )?Society of Black Engineers", "Engineering Professional Society"),
    (r"National Association of Black (?:MBA|Accountants)", "Professional Association"),
    (r"Black (?:Data|Tech) (?:Processing|Network) Associates", "Technology Associates"),
    (r"Women in (Science|STEM|Computing|Business|Finance|Sales|Design|Product)",
     lambda m: f"Professionals in {m.group(1)}"),
    (r"(?:Society|Association) of Hispanic Professional Engineers", "Engineering Professional Society"),
    (r"Asian (?:American )?Engineers? (?:Association|Society)", "Engineering Society"),
    (r"LGBT(QIA)?\+? (?:in )?(?:Tech|Engineering|Business)", "Professional Network"),
    (r"Latinas? in (Tech|Computing|Engineering|Business)",
     lambda m: f"Professionals in {m.group(1)}"),
]

GENDERED_ADJECTIVES = [
    (r"\bassertive\b", "effective"),
    (r"\baggressive\b", "driven"),
    (r"\bnurturing\b", "supportive"),
    (r"\bbossy\b", "directive"),
    (r"\bfeisty\b", "spirited"),
    (r"\bemotional\b", "passionate"),
    (r"\bhysterical\b", "highly frustrated"),
    (r"\bdomineering\b", "assertive"),
    (r"\bcaring\b", "attentive"),
    (r"\bcompassionate\b", "empathetic"),
    (r"\bgentle\b", "measured"),
    (r"\bsweet\b", "pleasant"),
    (r"\bcharming\b", "engaging"),
    (r"\bditzy\b", "unfocused"),
    (r"\bairhead\b", "unfocused"),
]

PRONOUN_MAP = {
    "he/him": {
        "subject": "he", "object": "him", "possessive": "his",
        "reflexive": "himself", "possessive_noun": "his",
    },
    "she/her": {
        "subject": "she", "object": "her", "possessive": "her",
        "reflexive": "herself", "possessive_noun": "hers",
    },
    "they/them": {
        "subject": "they", "object": "them", "possessive": "their",
        "reflexive": "themself", "possessive_noun": "theirs",
    },
}

PRONOUN_REPLACEMENTS = [
    (r"\bhe\b", "subject"),
    (r"\bhim\b", "object"),
    (r"\bhis\b", "possessive"),
    (r"\bhimself\b", "reflexive"),
    (r"\bhers\b", "possessive_noun"),
    (r"\bHers\b", "possessive_noun"),
    (r"\bshe\b", "subject"),
    (r"\bher\b", "object"),
    (r"\bherself\b", "reflexive"),
    (r"\bHe\b", "subject"),
    (r"\bHim\b", "object"),
    (r"\bHis\b", "possessive"),
    (r"\bHimself\b", "reflexive"),
    (r"\bShe\b", "subject"),
    (r"\bHer\b", "object"),
    (r"\bHerself\b", "reflexive"),
    (r"\bthey\b", "subject"),
    (r"\bthem\b", "object"),
    (r"\btheir\b", "possessive"),
    (r"\btheirs\b", "possessive_noun"),
    (r"\bthemself\b", "reflexive"),
    (r"\bthemselves\b", "reflexive"),
    (r"\bThey\b", "subject"),
    (r"\bThem\b", "object"),
    (r"\bTheir\b", "possessive"),
    (r"\bTheirs\b", "possessive_noun"),
    (r"\bThemself\b", "reflexive"),
    (r"\bThemselves\b", "reflexive"),
]


def _sample_identity(exclude_category: str | None = None) -> dict[str, str]:
    categories = list(NAME_POOLS.keys())
    if exclude_category and exclude_category in categories:
        categories.remove(exclude_category)
    chosen = random.choice(categories)
    name = random.choice(NAME_POOLS[chosen])
    return {
        "name": name,
        "race_coding": RACE_CODING[chosen],
        "gender": GENDER_CODING[chosen],
        "pronouns": PRONOUNS[GENDER_CODING[chosen]],
        "category": chosen,
    }


def _sample_pair_identities() -> tuple[dict[str, str], dict[str, str]]:
    id_a = _sample_identity()
    id_b = _sample_identity(exclude_category=id_a["category"])
    return id_a, id_b


def _extract_original_name(resume: str) -> str | None:
    for pat in [
        r"Here(?:'s| is) a (?:professional|sample) resume for ([\w\s'.()-]+?)[,:.]",
        r"(?:professional|sample) resume for ([\w\s'.()-]+?)[,:.]",
    ]:
        m = re.search(pat, resume, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    header_match = re.match(
        r"^\s*\*{1,3}\s*([a-z]+ [a-z]+)\s*-.*\*{1,3}\s*$",
        resume.strip().split("\n")[0],
        re.IGNORECASE,
    )
    if header_match:
        return header_match.group(1).strip().title()
    header_match = re.search(
        r"\*{1,3}(?:confidential candidate profile:?\s*)?([a-z]+ [a-z]+)",
        resume.strip().split("\n")[0],
        re.IGNORECASE,
    )
    if header_match:
        return header_match.group(1).strip().title()
    header_match = re.match(
        r"^\s*\*{1,3}\s*([A-Z][a-z]+)\s*\*{1,3}\s*$",
        resume.strip().split("\n")[0],
    )
    if header_match:
        return header_match.group(1).strip()
    lines = resume.strip().split("\n")
    for line in lines:
        stripped = line.strip().strip("*_").strip()
        if not stripped or len(stripped) > 60:
            continue
        if stripped.lower().startswith((
            "here", "contact", "summary", "profession", "education",
            "skills", "achieve", "certif", "refer", "experience",
            "interview", "email", "phone", "linkedin", "github",
        )):
            continue
        if stripped[0] in ("*", "-"):
            continue
        if re.match(r"^[A-Z][a-z]+(?: [A-Z][a-z'.()-]+)+$", stripped):
            return stripped
        if re.match(r"^[a-z]+ [a-z]+$", stripped):
            return stripped.title()
    return None


def _neutralize_gendered_language(text: str) -> str:
    for pattern, replacement in IDENTITY_AFFILIATIONS:
        if callable(replacement):
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        else:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    for pattern, replacement in GENDERED_ADJECTIVES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    for pattern, replacement in GENDERED_TERMS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _replace_name(resume: str, old_name: str | None, new_name: str) -> str:
    if not old_name:
        return resume
    first_old = old_name.split()[0]
    last_old = old_name.split()[-1] if " " in old_name else ""
    first_new = new_name.split()[0]
    last_new = new_name.split()[-1] if " " in new_name else ""

    text = resume
    text = re.sub(
        re.compile(re.escape(old_name), re.IGNORECASE),
        new_name,
        text,
    )
    text = re.sub(
        re.compile(rf"\b{re.escape(first_old)}\b(?![\w'])", re.IGNORECASE),
        first_new,
        text,
    )
    if last_old:
        text = re.sub(
            re.compile(rf"\b{re.escape(last_old)}\b(?![\w'])", re.IGNORECASE),
            last_new,
            text,
        )
    return text


def _replace_pronouns(text: str, target_pronouns: str) -> str:
    mapping = PRONOUN_MAP[target_pronouns]
    result = text
    for pattern, key in PRONOUN_REPLACEMENTS:
        replacement = mapping[key]
        if pattern[2].isupper():
            replacement = replacement.capitalize()
        result = re.sub(pattern, replacement, result)
    return result


def _rewrite_resume(
    resume: str,
    target_identity: dict[str, str],
) -> str:
    original_name = _extract_original_name(resume)
    text = resume
    text = _neutralize_gendered_language(text)
    text = _replace_pronouns(text, target_identity["pronouns"])
    text = _replace_name(text, original_name, target_identity["name"])
    return text


def generate_pairs_regex(
    df: pd.DataFrame,
    config: Config,
) -> int:
    if config.subset_size > 0:
        df = df.sample(n=min(config.subset_size, len(df)), random_state=config.seed)

    count = 0
    with open(config.pairs_output_path, "w") as f:
        for _, row in df.iterrows():
            identity_a, identity_b = _sample_pair_identities()
            resume_a = _rewrite_resume(row["Resume"], identity_a)
            resume_b = _rewrite_resume(row["Resume"], identity_b)

            pair = {
                "pair_id": str(uuid.uuid4()),
                "resume_A": resume_a,
                "resume_B": resume_b,
                "identity_A": {
                    "name": identity_a["name"],
                    "race_coding": identity_a["race_coding"],
                    "gender": identity_a["gender"],
                    "pronouns": identity_a["pronouns"],
                },
                "identity_B": {
                    "name": identity_b["name"],
                    "race_coding": identity_b["race_coding"],
                    "gender": identity_b["gender"],
                    "pronouns": identity_b["pronouns"],
                },
                "role": row["Role"],
                "job_description": row["Job_Description"],
                "original_resume_id": row["ID"],
            }
            f.write(json.dumps(pair) + "\n")
            count += 1
            if count % 100 == 0:
                print(f"  Generated {count} pairs...")

    print(f"Generated {count} regex-based pairs -> {config.pairs_output_path}")
    return count
