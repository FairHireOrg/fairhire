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

CLEAN_RESUME = """Jordan Ellis
jordan.ellis@example.com
(555) 987-6543
Austin, TX
linkedin.com/in/jordanellis

Summary
Backend engineer with 5 years of experience building reliable APIs.

Work Experience
Backend Engineer | Harbor Software | June 2021 – March 2024
- Built Python services handling 40M+ events per day
- Designed REST APIs used by 200 customers
- Reduced deploy time by 30% with Docker automation

Education
B.S. Computer Science, River Valley University | May 2021

Skills
Python, PostgreSQL, REST APIs, Docker, Kubernetes, AWS, Git
"""

# Simulates `pdftotext -layout` output for a two-column template: wide
# interior gaps scramble the reading order for parsers.
MULTICOLUMN_RESUME = """Jordan Ellis                    jordan.ellis@example.com
(555) 987-6543                    Austin, TX

Summary                    Backend engineer building APIs.
Work Experience                    Harbor Software
Backend Engineer                    June 2021 – March 2024
- Built Python services                    handling 40M+ events
- Designed REST APIs                    used by 200 customers
Education                    River Valley University
B.S. Computer Science                    May 2021
Skills                    Python, Docker, AWS, Git
"""

CREATIVE_RESUME = """Jordan Ellis
jordan.ellis@example.com
(555) 987-6543
Austin, TX

My Journey
Backend engineer with 5 years of experience building reliable APIs.

What I Do Best
Backend Engineer | Harbor Software | June 2021 – March 2024
- Built Python services handling 40M+ events per day

Toolbox
Python, PostgreSQL, REST APIs, Docker, AWS, Git
"""

DECORATIVE_RESUME = """Jordan Ellis
jordan.ellis@example.com
(555) 987-6543
Austin, TX

Summary
Backend engineer with 5 years of experience building reliable APIs.

Experience
Backend Engineer | Harbor Software | June 2021 – March 2024
➔ Built Python services handling 40M+ events per day
✓ Designed REST APIs used by 200 customers
★ Reduced deploy time by 30% with Docker automation

Education
B.S. Computer Science, River Valley University

Skills
Python, PostgreSQL, REST APIs, Docker, AWS, Git
"""

MIXED_DATES_RESUME = """Jordan Ellis
jordan.ellis@example.com
(555) 987-6543
Austin, TX

Summary
Backend engineer with 5 years of experience.

Experience
Backend Engineer | Harbor Software | June 2021 – March 2024
- Built Python services handling 40M+ events per day

Software Engineer | FinTech Co. | 2019-2021
- Designed REST APIs used by 200 customers

Education
B.S. Computer Science, River Valley University

Skills
Python, PostgreSQL, REST APIs, Docker, AWS, Git
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
    check("sentence slices are exact", all(text[s.start:s.end] == s.text for s in sentences))

    indented = "Header\n   - Built REST APIs with Python.\n  A second sentence. Another one."
    check(
        "indented sentence slices are exact",
        all(indented[s.start:s.end] == s.text for s in segment_sentences(indented)),
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


def test_soft_ability_quarantine() -> None:
    """Soft/ability requirements only match on strong, curated evidence.

    A loose token overlap (e.g. "team") must not auto-verify an ability
    requirement in the keyword-relevance view; without curated evidence it is
    surfaced as unmatched.
    """
    from fairhire.fitness.rubric import score_resume

    jd_text = "Engineer\nRequirements\n- Strong collaboration with the engineering team"
    d = score_resume(RESUME, jd_text).to_dict()
    soft = [t for t in d["keyword_groups"] if t["kind"] == "soft"]
    check("soft requirement surfaced", len(soft) >= 1)
    check("soft ability not auto-matched without curated evidence",
          all(not t["matched"] for t in soft))


def test_determinism() -> None:
    a = analyze_fitness(job_description=JD, resume_text=RESUME)
    b = analyze_fitness(job_description=JD, resume_text=RESUME)
    check("identical ats score", a["ats_score"] == b["ats_score"])
    check("identical ats grade", a["ats_grade"] == b["ats_grade"])
    check("identical dimensions", json.dumps(a["dimensions"]) == json.dumps(b["dimensions"]))
    check("identical recommendations", json.dumps(a["recommendations"]) == json.dumps(b["recommendations"]))
    check("identical keyword coverage", a["keyword_coverage"] == b["keyword_coverage"])
    check("identical keyword groups", json.dumps(a["keyword_groups"]) == json.dumps(b["keyword_groups"]))
    check("ats score is a finite percentage", isinstance(a["ats_score"], (int, float)) and 0 <= a["ats_score"] <= 100)


def test_ats_resume_only_and_deterministic() -> None:
    """The ATS score is resume-only: a different JD must not change it."""
    from fairhire.fitness.rubric import score_resume

    d1 = score_resume(RESUME, JD).to_dict()
    d2 = score_resume(RESUME, "Completely different role. Requirements- Java and microservices.").to_dict()
    check("ats score ignores the job description", d1["ats_score"] == d2["ats_score"])
    check("ats grade present", isinstance(d1["ats_grade"], str) and d1["ats_grade"])
    check("actions are actionable", all(bool(r["severity"] in {"high", "medium", "low"} and r["action"]) for r in d1["recommendations"]))


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
    check("deterministic mode when no key", result["extraction_status"] == "deterministic_only")
    check("vector still surfaces SQL->PostgreSQL relevance",
          any(g["term"] == "SQL" and g["matched"] and g["resume_term"] == "PostgreSQL"
              for g in result["keyword_groups"]))


def test_deterministic_checklist_path() -> None:
    """The deterministic rule-based checklist drives the keyword relevance view.

    Scoring is fully resume-only; the (optional) AI suggestion endpoint is a
    separate review step and is never on the scoring path.
    """
    from fairhire.config import Config
    from fairhire.fitness.rubric import score_resume

    checklist_jd = """Backend Engineer
Requirements
- Bachelor's degree in Computer Science
- Strong analytical and problem-solving skills
- Experience with message queues (Kafka)
Nice to have
- Familiarity with healthcare software
"""
    cfg = Config(deepseek_api_key="dummy")
    d = score_resume(RESUME, checklist_jd, config=cfg).to_dict()
    check("deterministic extraction status", d["extraction_status"] == "deterministic_only")
    check("degree keyword matched", any(
        g["matched"] and g["kind"] == "degree" for g in d["keyword_groups"]))
    check("Kafka keyword matched", any(
        g["matched"] and "Kafka" in g["term"] for g in d["keyword_groups"]))
    check("soft surfaced but not auto-verified", any(
        not g["matched"] and g["kind"] == "soft" for g in d["keyword_groups"]))


def test_ats_clean_resume_scores_strong() -> None:
    from fairhire.fitness.ats import evaluate_ats

    r = evaluate_ats(parse_resume(CLEAN_RESUME))
    check("clean resume scores Strong (>=80)", r.score >= 80)
    check("clean resume has no high recommendations",
          all(rec.severity != "high" for rec in r.recommendations))
    codes = {rec.code for rec in r.recommendations}
    for absent in ("layout_columns", "creative_headings", "decorative_bullets",
                   "no_email", "no_phone", "no_skills", "no_experience"):
        check(f"clean resume has no {absent} rec", absent not in codes)
    by = {d.key: d for d in r.dimensions}
    check("parser-safe family sums to ~0.55",
          abs(sum(d.weight for d in r.dimensions if d.family == "parser_safe") - 0.55) < 1e-9)
    check("extraction family sums to ~0.45",
          abs(sum(d.weight for d in r.dimensions if d.family == "extraction") - 0.45) < 1e-9)
    check("clean layout is 100", by["layout"].score == 100.0)
    check("clean bullets are 100", by["bullet_style"].score == 100.0)
    check("month-year dates are 100", by["date_format"].score == 100.0)


def test_ats_multicolumn_layout_flagged() -> None:
    from fairhire.fitness.ats import evaluate_ats

    bad = evaluate_ats(parse_resume(MULTICOLUMN_RESUME))
    good = evaluate_ats(parse_resume(CLEAN_RESUME))
    codes = {rec.code for rec in bad.recommendations}
    check("multicolumn emits layout_columns", "layout_columns" in codes)
    by = {d.key: d for d in bad.dimensions}
    check("multicolumn layout scores low", by["layout"].score < 60)
    check("multicolumn scores below clean", bad.score < good.score)
    rec = next(rec for rec in bad.recommendations if rec.code == "layout_columns")
    check("layout rec has offsets", rec.start >= 0 and rec.end > rec.start and rec.line >= 1)


def test_ats_creative_headings_flagged() -> None:
    from fairhire.fitness.ats import evaluate_ats

    r = evaluate_ats(parse_resume(CREATIVE_RESUME))
    codes = {rec.code for rec in r.recommendations}
    check("creative resume emits creative_headings", "creative_headings" in codes)
    by = {d.key: d for d in r.dimensions}
    check("creative resume still recovers dated roles", by["chronology"].score > 0)
    rec = next(rec for rec in r.recommendations if rec.code == "creative_headings")
    check("creative rec points at the heading",
          "My Journey" in CREATIVE_RESUME[rec.start:rec.end] and rec.line >= 1)
    check("creative resume scores below clean",
          r.score < evaluate_ats(parse_resume(CLEAN_RESUME)).score)


def test_ats_decorative_bullets_flagged() -> None:
    from fairhire.fitness.ats import evaluate_ats

    r = evaluate_ats(parse_resume(DECORATIVE_RESUME))
    codes = {rec.code for rec in r.recommendations}
    check("decorative resume emits decorative_bullets", "decorative_bullets" in codes)
    by = {d.key: d for d in r.dimensions}
    check("decorative bullet_style penalized", by["bullet_style"].score <= 40)
    rec = next(rec for rec in r.recommendations if rec.code == "decorative_bullets")
    check("decorative rec points at the bullet",
          "➔" in DECORATIVE_RESUME[rec.start:rec.end] and rec.line >= 1)


def test_ats_mixed_dates_flagged() -> None:
    from fairhire.fitness.ats import evaluate_ats

    r = evaluate_ats(parse_resume(MIXED_DATES_RESUME))
    codes = {rec.code for rec in r.recommendations}
    check("mixed dates emit mixed_dates", "mixed_dates" in codes)
    by = {d.key: d for d in r.dimensions}
    check("mixed dates score below month-year-only",
          by["date_format"].score < 100)


def test_ats_recommendation_offsets_sane() -> None:
    from fairhire.fitness.ats import evaluate_ats

    for fixture in (CLEAN_RESUME, MULTICOLUMN_RESUME, CREATIVE_RESUME,
                    DECORATIVE_RESUME, MIXED_DATES_RESUME, RESUME):
        r = evaluate_ats(parse_resume(fixture))
        for rec in r.recommendations:
            if rec.start >= 0:
                check(f"offset slice valid ({rec.code})",
                      0 <= rec.start < rec.end <= len(fixture) and rec.line >= 1)
            check(f"action present ({rec.code})", bool(rec.action))
            check(f"severity valid ({rec.code})", rec.severity in {"high", "medium", "low"})


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
    test_soft_ability_quarantine()
    print("Determinism")
    test_determinism()
    print("Feature extraction")
    test_features()
    print("ATS resume-only")
    test_ats_resume_only_and_deterministic()
    print("Deterministic fallback (no LLM)")
    test_deterministic_fallback_without_llm()
    print("Deterministic checklist path")
    test_deterministic_checklist_path()
    print("ATS clean resume")
    test_ats_clean_resume_scores_strong()
    print("ATS multicolumn layout")
    test_ats_multicolumn_layout_flagged()
    print("ATS creative headings")
    test_ats_creative_headings_flagged()
    print("ATS decorative bullets")
    test_ats_decorative_bullets_flagged()
    print("ATS mixed dates")
    test_ats_mixed_dates_flagged()
    print("ATS recommendation offsets")
    test_ats_recommendation_offsets_sane()
    print("\nAll tests passed.")
