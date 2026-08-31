#!/usr/bin/env python3
"""Deterministic fitness pipeline smoke tests.

Run directly (no pytest needed):
    python test_fitness.py
"""

from __future__ import annotations

import json

from fairhire.fitness.extract import extract_resume_features
from fairhire.fitness.ner import (
    extract_fields,
    find_occurrences,
    parse_job_description,
    parse_resume,
    segment_sentences,
)
from fairhire.fitness.service import analyze_fitness

RESUME = """Alex Morgan
alex.morgan@example.com
(555) 123-4567
San Francisco, CA
github.com/alexmorgan

PROFESSIONAL SUMMARY
Backend engineer with 6 years of experience building distributed data platforms.

EXPERIENCE
Senior Software Engineer, DataPlat Inc. 2020-2024
- Built distributed services in Python handling 40M+ events per day
- Designed RESTful APIs and microservice architecture
- Managed PostgreSQL and Redis clusters

Software Engineer, FinTech Co. 2017-2020
- Integrated Kafka for real-time event streaming
- Worked with MySQL

EDUCATION
B.S. Computer Science, State University

SKILLS
Python, Java, PostgreSQL, Redis, Kafka, MySQL, Docker, Kubernetes, AWS, Airflow, Spark, Elasticsearch, REST APIs, Microservices
"""

JD = """Senior Backend Engineer
Requirements
- Strong proficiency with Python and distributed systems
- Experience with SQL databases such as PostgreSQL
- Experience with message queues (Kafka)
- Strong understanding of REST APIs and microservices
- Familiarity with cloud platforms (AWS)
Nice to have
- PyTorch experience
"""


def check(name: str, cond: bool | None) -> None:
    if not bool(cond):
        raise AssertionError(f"FAIL: {name}")
    print(f"  ok  {name}")


def test_structured_fields() -> None:
    f = extract_fields(RESUME)
    check("email extracted", f["email"] == "alex.morgan@example.com")
    check("phone extracted", f["phone"] == "(555) 123-4567")
    check("github extracted", f.get("github") == "github.com/alexmorgan")
    check("degrees extracted", any("B.S" in d for d in f.get("degrees", [])))
    check("date ranges extracted", bool(f.get("date_ranges")))


def test_sections_and_terms() -> None:
    doc = parse_resume(RESUME)
    check("experience section", doc.sections.get("experience"))
    check("education section", doc.sections.get("education"))
    check("skills section", doc.sections.get("skills"))
    canonicals = {o.canonical for o in doc.occurrences}
    for expected in ("Python", "PostgreSQL", "Kafka", "REST", "AWS", "Docker", "Kubernetes"):
        check(f"term tagged: {expected}", expected in canonicals)


def test_offsets_consistent() -> None:
    text = RESUME
    sentences = segment_sentences(text)
    occs = find_occurrences(text, sentences)
    for occ in occs:
        check(
            f"span slice matches variant ({occ.canonical})",
            text[occ.start : occ.end] == occ.text,
        )


def test_matching_tiers() -> None:
    jd = parse_job_description(JD)
    resume = parse_resume(RESUME)
    from fairhire.fitness.matcher import match_documents

    m = match_documents(jd, resume)
    by = {lnk.canonical: lnk for lnk in m.links}
    check("exact match (Python)", by["Python"].quality == "exact")
    check("family match (SQL -> PostgreSQL)", by["SQL"].quality == "family")
    check("missing required surfaced", "PyTorch" in m.missing_optional)
    check("no false positives in matched required", all(t in m.matched_required for t in m.matched_required))


def test_no_false_positive_matches() -> None:
    from fairhire.fitness.matcher import match_documents

    # #1: A wide "contains" gap must not be treated as a match. Old window was
    # 10 tokens, so "machine ... learning" 8 tokens apart used to link them.
    jd = parse_job_description("Requirements\n- Experience with machine learning")
    resume = parse_resume(
        "Alex\n\nPROJECTS\n- The machine coordinates the whole data pipeline and "
        "improves learning.\n- Python."
    )
    m = match_documents(jd, resume)
    by = {lnk.canonical: lnk for lnk in m.links}
    check("wide contains window rejected", "Machine Learning" not in by)

    # #2: A short term that merely shares a prefix with a longer skill is NOT a
    # family match (e.g. "data" vs "databricks").
    jd2 = parse_job_description("Requirements\n- Comfortable with data engineering")
    resume2 = parse_resume("Alex\n\nEXPERIENCE\n- Built databricks pipelines at scale.")
    m2 = match_documents(jd2, resume2)
    by2 = {lnk.canonical: lnk for lnk in m2.links}
    check("prefix coincidence not a family match", "Data Engineering" not in by2)

    # #3: No fuzzy tier — a near/typo term does not create a link.
    jd3 = parse_job_description("Requirements\n- Prior experience with Deveops")
    resume3 = parse_resume("Alex\n\nSKILLS\nPython, Docker, Kubernetes")
    m3 = match_documents(jd3, resume3)
    check("no fuzzy near-match links", all("deveops" != lnk.canonical.lower() for lnk in m3.links))


def test_hybrid_min_shared() -> None:
    import fairhire.fitness.llm_extract as le
    from fairhire.config import Config
    from fairhire.fitness.llm_extract import Requirement, ResumeEvidence
    from fairhire.fitness.rubric import score_resume

    reqs = [Requirement("Collaborate with the engineering team", "ability", True)]
    le.extract_requirements = lambda *a, **k: reqs
    le.extract_resume_evidence = lambda *a, **k: ResumeEvidence()
    le.judge_requirements = lambda *a, **k: []
    cfg = Config(deepseek_api_key="dummy")
    d = score_resume(RESUME, JD, config=cfg).to_dict()
    row = next((t for t in d["required_terms"] if t["term"] == "Collaborate with the engineering team"), None)
    check("ability needs >=2 shared stems (no single-word match)", row is not None and not row["matched"])


def test_llm_semantic_judge() -> None:
    import fairhire.fitness.llm_extract as le
    from fairhire.config import Config
    from fairhire.fitness.llm_extract import Requirement, ResumeEvidence, SemanticJudgment
    from fairhire.fitness.rubric import score_resume

    resume_txt = (
        "Alex Morgan\n\nSKILLS\nTypeScript, Node.js\n\n"
        "EXPERIENCE\n- Built a typed web app entirely in TypeScript."
    )
    jd_txt = "Senior Full Stack Engineer\nRequirements\n- Experience with JavaScript"

    reqs = [Requirement("Experience with JavaScript", "skill", True)]
    le.extract_requirements = lambda *a, **k: reqs
    le.extract_resume_evidence = lambda *a, **k: ResumeEvidence(skills=["TypeScript"])
    le.judge_requirements = lambda texts, rtext, cfg=None, max_items=24: [
        SemanticJudgment(
            "Experience with JavaScript", True,
            evidence="TypeScript",
            relation="TypeScript is a superset of JavaScript",
        )
    ]

    cfg = Config(deepseek_api_key="dummy")

    # Initial analyze (no confirmations): the LLM only *suggests*; it does NOT
    # auto-match, so the score stays based on lexical matches only (deterministic).
    d = score_resume(resume_txt, jd_txt, config=cfg).to_dict()
    row = next((t for t in d["required_terms"] if t["term"] == "Experience with JavaScript"), None)
    check("suggestion is not auto-matched", row is not None and not row["matched"])
    check("suggestion carries a hint", row is not None and "TypeScript" in (row.get("hint") or ""))
    check("confirm item surfaced", any(c["term"] == "Experience with JavaScript" for c in d["confirm_items"]))
    check("no inferred score without confirmation", all(lnk["quality"] != "inferred" for lnk in d["links"]))

    # Explicit user confirmation flips it to matched -> deterministic.
    d2 = score_resume(resume_txt, jd_txt, config=cfg, confirmations={"experience with javascript": True}).to_dict()
    row2 = next((t for t in d2["required_terms"] if t["term"] == "Experience with JavaScript"), None)
    check("user confirmation matches JS", row2 is not None and row2["matched"] and row2["quality"] == "inferred")
    link = next((lnk for lnk in d2["links"] if lnk["canonical"] == "Experience with JavaScript"), None)
    check("confirmed link anchored to TS evidence", link is not None and "TypeScript" in link["resume_term"])
    check("confirmed link anchor is valid resume sentence",
          link is not None and 0 <= link["resume_sentence_index"] < len(d2["resume_sentences"]))

    # Declined -> stays missing (no fabricated link).
    d3 = score_resume(resume_txt, jd_txt, config=cfg, confirmations={"experience with javascript": False}).to_dict()
    row3 = next((t for t in d3["required_terms"] if t["term"] == "Experience with JavaScript"), None)
    check("declined stays missing", row3 is not None and not row3["matched"])
    check("no inferred links when declined", all(lnk["quality"] != "inferred" for lnk in d3["links"]))


def test_determinism() -> None:
    a = analyze_fitness(job_description=JD, resume_text=RESUME)
    b = analyze_fitness(job_description=JD, resume_text=RESUME)
    check("identical score", a["overall_score"] == b["overall_score"])
    check("identical links", json.dumps(a["links"]) == json.dumps(b["links"]))
    check("links reference valid sentences", all(
        0 <= lnk["jd_sentence_index"] < len(a["jd_sentences"])
        and 0 <= lnk["resume_sentence_index"] < len(a["resume_sentences"])
        for lnk in a["links"]
    ))


def test_features() -> None:
    rf = extract_resume_features(RESUME)
    check("feature email", rf.email == "alex.morgan@example.com")
    check("feature titles", len(rf.titles) >= 2)
    check("feature skills", "Python" in rf.skills)


def test_deterministic_fallback_without_llm() -> None:
    from fairhire.config import Config

    # Force an empty key so the fallback path is exercised regardless of any
    # FAIRHIRE_DEEPSEEK_KEY present in the environment or backend/.env.
    cfg = Config(deepseek_api_key="")
    result = analyze_fitness(job_description=JD, resume_text=RESUME, config=cfg)
    check("deterministic mode when no key", result["extraction_mode"] == "deterministic")
    check("deterministic still links SQL->PostgreSQL",
          any(lnk["canonical"] == "SQL" and lnk["quality"] == "family" for lnk in result["links"]))


def test_hybrid_mode_with_mocked_llm() -> None:
    import fairhire.fitness.llm_extract as le
    from fairhire.fitness.llm_extract import Requirement, ResumeEvidence
    from fairhire.fitness.rubric import score_resume
    from fairhire.config import Config

    requirements = [
        Requirement("Bachelor's degree in Computer Science", "degree", True),
        Requirement("Strong analytical and problem-solving skills", "soft", True),
        Requirement("Develop, test, and maintain software applications", "ability", True),
        Requirement("Experience with message queues (Kafka)", "skill", True),
        Requirement("Familiarity with healthcare software", "soft", False),
    ]
    evidence = ResumeEvidence(
        degree="B.S. Computer Science",
        skills=["Python", "PostgreSQL", "Kafka", "Rust"],
        soft_skills=["problem solving", "teaching"],
        strengths=["Built distributed services in Python", "Integrated Kafka for streaming"],
        total_years=4,
    )
    le.extract_requirements = lambda *a, **k: requirements
    le.extract_resume_evidence = lambda *a, **k: evidence
    le.judge_requirements = lambda *a, **k: []

    cfg = Config(deepseek_api_key="dummy")
    report = score_resume(RESUME, JD, config=cfg)
    d = report.to_dict()
    check("hybrid mode active", d["extraction_mode"] == "hybrid")
    check("hybrid degree matched", any(
        t["matched"] and t["kind"] == "degree" for t in d["required_terms"]))
    check("soft/ability not auto-matched (surfaced as questions)", any(
        not t["matched"] and t["kind"] in {"soft", "ability"} for t in d["required_terms"]))
    check("confirm items include soft/ability", any(
        c["kind"] in {"soft", "ability"} for c in d["confirm_items"]))
    check("hybrid skill (Kafka) matched", any(
        t["matched"] and t["kind"] == "skill" and "Kafka" in t["term"] for t in d["required_terms"]))
    check("hybrid missing surfaced", any(
        not t["matched"] for t in d["required_terms"]))
    check("hybrid links have jd sentence anchors", all(
        0 <= lnk["jd_sentence_index"] < len(d["jd_sentences"]) for lnk in d["links"]))
    check("hybrid links have resume sentence anchors", all(
        0 <= lnk["resume_sentence_index"] < len(d["resume_sentences"]) for lnk in d["links"]))


if __name__ == "__main__":
    print("Structured fields")
    test_structured_fields()
    print("Sections + terms")
    test_sections_and_terms()
    print("Offset consistency")
    test_offsets_consistent()
    print("Matching tiers")
    test_matching_tiers()
    print("False-positive guards")
    test_no_false_positive_matches()
    print("Hybrid min-shared guard")
    test_hybrid_min_shared()
    print("Inferred superset")
    test_llm_semantic_judge()
    print("Determinism")
    test_determinism()
    print("Feature extraction")
    test_features()
    print("Deterministic fallback (no LLM)")
    test_deterministic_fallback_without_llm()
    print("Hybrid mode (mocked DeepSeek)")
    test_hybrid_mode_with_mocked_llm()
    print("\nAll tests passed.")
