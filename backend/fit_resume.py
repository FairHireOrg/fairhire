#!/usr/bin/env python3
"""CLI for deterministic Resume–JD fitness scoring."""

from __future__ import annotations

import argparse
import json
import sys

from fairhire.fitness.service import analyze_fitness


def main() -> None:
    parser = argparse.ArgumentParser(description="FairHire Resume–JD fitness (deterministic)")
    parser.add_argument("resume", help="Path to resume PDF/TXT, or '-' for stdin text")
    parser.add_argument("--jd", required=True, help="Path to job description text file")
    parser.add_argument("--json", action="store_true", help="Print full JSON")
    args = parser.parse_args()

    with open(args.jd, encoding="utf-8") as f:
        jd = f.read()

    if args.resume == "-":
        resume_text = sys.stdin.read()
        result = analyze_fitness(job_description=jd, resume_text=resume_text)
    else:
        result = analyze_fitness(job_description=jd, resume_path=args.resume)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("=" * 60)
    print("FairHire — Resume–JD Fitness")
    print("=" * 60)
    print(f"Overall: {result['overall_score']:.1f}  |  extraction={result['extraction_mode']}")
    if result.get("job_title"):
        print(f"JD title: {result['job_title']}")
    print()
    for dim in result["dimensions"]:
        print(f"  {dim['label']:<24} {dim['score']:5.1f}  (w={dim['weight']:.2f})  {dim['detail']}")
    print()
    print("Requirements:")
    for row in result["required_terms"]:
        mark = "MATCH" if row["matched"] else "missing"
        quality = f" ({row['quality']})" if row["matched"] else ""
        print(f"  [{row['kind']:>7} {'req':>3}] {row['term'][:64]:<64} {mark}{quality}")
    for row in result["optional_terms"]:
        mark = "MATCH" if row["matched"] else "missing"
        print(f"  [{row['kind']:>7} {'opt':>3}] {row['term'][:64]:<64} {mark}")
    print()
    if result["blockers"]:
        print("Blockers:")
        for b in result["blockers"]:
            print(f"  [{b['severity']}] {b['message']}")
            print(f"           → {b['suggestion']}")
    print()
    print("Matched links:")
    for link in result["links"][:15]:
        mark = "required" if link["required"] else "optional"
        print(f"  {link['jd_term'][:36]:<36} [{mark} {link['quality']:>9}] -> {link['resume_term']}")
    print()
    missing = result["missing_required"]
    print("Missing required:", ", ".join(missing[:12]) or "(none)")
    print()
    print(result["disclaimer"])


if __name__ == "__main__":
    main()
