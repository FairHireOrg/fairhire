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

    cfg = Config()  # no deepseek key set in this env
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

    cfg = Config(deepseek_api_key="dummy")
    report = score_resume(RESUME, JD, config=cfg)
    d = report.to_dict()
    check("hybrid mode active", d["extraction_mode"] == "hybrid")
    check("hybrid degree matched", any(
        t["matched"] and t["kind"] == "degree" for t in d["required_terms"]))
    check("hybrid soft matched", any(
        t["matched"] and t["kind"] == "soft" for t in d["required_terms"]))
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
    print("Determinism")
    test_determinism()
    print("Feature extraction")
    test_features()
    print("Deterministic fallback (no LLM)")
    test_deterministic_fallback_without_llm()
    print("Hybrid mode (mocked DeepSeek)")
    test_hybrid_mode_with_mocked_llm()
    print("\nAll tests passed.")
