import argparse
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any

import numpy as np
import torch
from scipy import stats as scipy_stats
from sentence_transformers import SentenceTransformer

from fairhire.config import Config
from fairhire.identity import predict_gender
from fairhire.parser import parse_pdf
from fairhire.stage1.name_pools import (
    NAME_POOLS,
    RACE_CODING,
    GENDER_CODING,
    PRONOUNS,
)
from fairhire.stage1.regex_generator import (
    _extract_original_name,
)
from fairhire.stage2.screener import Screener

DEFAULT_JD = (
    "We are looking for a skilled Software Engineer to join our engineering team. "
    "You will design, develop, and maintain scalable software solutions, collaborate "
    "with cross-functional teams, and contribute to architectural decisions. The ideal "
    "candidate has strong programming skills, experience with modern frameworks, and a "
    "passion for building high-quality software."
)


def _mutate_resume(resume: str, target_identity: dict[str, str]) -> str:
    original_name = _extract_original_name(resume)
    new_name = target_identity["name"]
    new_first = new_name.split()[0].lower()
    new_last = new_name.split()[-1].lower()
    new_email_key = new_first + new_last

    lines = resume.split("\n")
    result = []
    name_replaced = False
    contact_done = False

    for line in lines:
        stripped = line.strip()

        if not name_replaced and stripped and stripped == original_name:
            result.append(new_name)
            name_replaced = True
            continue

        if not contact_done and ("@" in line and "linkedin" in line.lower()):
            new_line = line
            new_line = re.sub(
                r"[\w.]+@[\w.]+",
                f"{new_email_key}@gmail.com",
                new_line,
            )
            new_line = re.sub(
                r"linkedin\.com/in/[\w.]+",
                f"linkedin.com/in/{new_email_key}",
                new_line,
            )
            result.append(new_line)
            contact_done = True
            continue

        result.append(line)

    return "\n".join(result)


def _generate_variants(
    resume_text: str,
    num_variants: int,
) -> list[dict[str, Any]]:
    all_categories = list(NAME_POOLS.keys())
    variants = []
    for _ in range(num_variants):
        category = all_categories[len(variants) % len(all_categories)]
        name = NAME_POOLS[category][len(variants) % len(NAME_POOLS[category])]
        race = RACE_CODING[category]
        gender = GENDER_CODING[category]
        pronouns = PRONOUNS[gender]
        identity = {
            "name": name,
            "race_coding": race,
            "gender": gender,
            "pronouns": pronouns,
            "category": category,
        }
        mutated = _mutate_resume(resume_text, identity)
        variants.append({
            "index": len(variants),
            "identity": identity,
            "resume_text": mutated,
        })
    return variants


def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    s1, s2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return float((np.mean(group1) - np.mean(group2)) / pooled_std)


def main():
    parser = argparse.ArgumentParser(description="FairHire AI — Counterfactual Resume Audit")
    parser.add_argument("pdf", help="Path to PDF resume")
    parser.add_argument("--num-variants", type=int, default=200,
                        help="Number of identity variants to generate (default: 200)")
    parser.add_argument("--role", type=str, default="software engineer",
                        help="Target role for scoring (default: software engineer)")
    parser.add_argument("--job-description", type=str, default=None,
                        help="Custom job description text (overrides --role)")
    parser.add_argument("--output-csv", type=str, default="audit_results.csv",
                        help="Save variant scores to CSV (default: audit_results.csv)")
    args = parser.parse_args()

    config = Config()

    print("=" * 70)
    print("FAIRHIRE AI — COUNTERFACTUAL RESUME AUDIT")
    print("=" * 70)

    print(f"\n[1/4] Parsing PDF: {args.pdf}")
    resume_text = parse_pdf(args.pdf)
    print(f"  Extracted {len(resume_text):,} characters")

    original_name = _extract_original_name(resume_text)
    first_name = original_name.split()[0].lower() if original_name else "unknown"
    print(f"  Detected name: {original_name}")
    print(f"  First name context: {first_name}")

    jd_text = args.job_description if args.job_description else DEFAULT_JD
    role_label = args.role

    print(f"\n[2/4] Generating {args.num_variants} identity variants...")
    variants = _generate_variants(resume_text, args.num_variants)
    print(f"  Generated {len(variants)} variants")

    race_counts: dict[str, int] = defaultdict(int)
    gender_counts: dict[str, int] = defaultdict(int)
    for v in variants:
        race_counts[v["identity"]["race_coding"]] += 1
        gender_counts[v["identity"]["gender"]] += 1

    print(f"\n[3/4] Scoring variants against role: {role_label}")
    print(f"  Loading screener model: {config.model_output_path}")
    if not os.path.exists(config.model_output_path):
        print(f"  ERROR: Model not found at {config.model_output_path}")
        print(f"  Run training first: python run_pipeline.py")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")
    print(f"  Loading embedder: {config.embedding_model}")
    embedder = SentenceTransformer(config.embedding_model, device=device)

    model = Screener(embedding_dim=config.embedding_dim).to(device)
    model.load_state_dict(
        torch.load(config.model_output_path, map_location=device, weights_only=True)
    )
    model.eval()

    job_emb = embedder.encode([jd_text], convert_to_tensor=True, show_progress_bar=False).to(device)
    resume_texts = [v["resume_text"] for v in variants]
    resume_embs = embedder.encode(
        resume_texts,
        batch_size=config.batch_size,
        show_progress_bar=True,
        convert_to_tensor=True,
    ).to(device)

    with torch.no_grad():
        scores = model(resume_embs, job_emb.expand(len(variants), -1)).cpu().numpy()

    for v, score in zip(variants, scores):
        v["score"] = float(score)

    baseline_job = job_emb
    baseline_resume = embedder.encode([resume_text], convert_to_tensor=True, show_progress_bar=False).to(device)
    with torch.no_grad():
        baseline_score = model(baseline_resume, baseline_job).item()

    print(f"\n[4/4] Results")

    scores_arr = np.array([v["score"] for v in variants])
    print(f"\n{'Score Distribution':─^60}")
    print(f"  Your original resume:  {baseline_score:.8f}")
    print(f"  Variant mean:          {scores_arr.mean():.8f}")
    print(f"  Variant std:           {scores_arr.std():.8f}")
    print(f"  Min / Max:             {scores_arr.min():.8f} / {scores_arr.max():.8f}")
    print(f"  Score range:           {scores_arr.max() - scores_arr.min():.8f}")

    race_groups: dict[str, list[float]] = defaultdict(list)
    gender_groups: dict[str, list[float]] = defaultdict(list)
    for v in variants:
        race_groups[v["identity"]["race_coding"]].append(v["score"])
        gender_groups[v["identity"]["gender"]].append(v["score"])

    print(f"\n{'Race Breakdown':─^60}")
    races_sorted = sorted(race_groups.keys(),
                          key=lambda r: np.mean(race_groups[r]), reverse=True)
    print(f"  {'Race':<12} {'Count':>5} {'Mean':>12}  {'Std':>12}")
    for race in races_sorted:
        a = np.array(race_groups[race])
        print(f"  {race:<12} {len(a):>5} {np.mean(a):>12.8f}  {np.std(a):>12.8f}")

    all_race_scores = [np.array(race_groups[r]) for r in races_sorted]
    if len(all_race_scores) >= 2:
        f_stat, p_race = scipy_stats.f_oneway(*all_race_scores)
        print(f"\n  One-way ANOVA: F={f_stat:.4f}, p={p_race:.6f}")
        if p_race < 0.05:
            print(f"    SIGNIFICANT — race has a detectable effect on fit scores")
        else:
            print(f"    NOT SIGNIFICANT")

        print(f"\n  Pairwise t-tests (race):")
        for i, r1 in enumerate(races_sorted):
            for r2 in races_sorted[i + 1:]:
                g1 = np.array(race_groups[r1])
                g2 = np.array(race_groups[r2])
                t_stat, p_val = scipy_stats.ttest_ind(g1, g2)
                d = _cohens_d(g1, g2)
                sig = "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
                print(f"    {r1:<10} vs {r2:<10}  t={t_stat:>7.3f}  p={p_val:.5f}  d={d:>6.3f}  [{sig}]")

    print(f"\n{'Gender Breakdown':─^60}")
    genders_sorted = sorted(gender_groups.keys())
    print(f"  {'Gender':<12} {'Count':>5} {'Mean':>12}  {'Std':>12}")
    for gender in genders_sorted:
        a = np.array(gender_groups[gender])
        print(f"  {gender:<12} {len(a):>5} {np.mean(a):>12.8f}  {np.std(a):>12.8f}")

    all_gender_scores = [np.array(gender_groups[g]) for g in genders_sorted]
    if len(all_gender_scores) >= 2:
        f_stat, p_gender = scipy_stats.f_oneway(*all_gender_scores)
        print(f"\n  One-way ANOVA: F={f_stat:.4f}, p={p_gender:.6f}")
        if p_gender < 0.05:
            print(f"    SIGNIFICANT")
        else:
            print(f"    NOT SIGNIFICANT")

        if len(all_gender_scores) == 2:
            g1, g2 = all_gender_scores[0], all_gender_scores[1]
            t_stat, p_val = scipy_stats.ttest_ind(g1, g2)
            d = _cohens_d(g1, g2)
            sig = "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
            print(f"    {genders_sorted[0]:<10} vs {genders_sorted[1]:<10}  t={t_stat:>7.3f}  p={p_val:.5f}  d={d:>6.3f}  [{sig}]")

    print(f"\n{'Disparity by Race Pairing':─^60}")
    pair_disparities: dict[str, list[float]] = defaultdict(list)
    for i, va in enumerate(variants):
        for j, vb in enumerate(variants):
            if i >= j:
                continue
            races = frozenset((va["identity"]["race_coding"], vb["identity"]["race_coding"]))
            if len(races) > 1:
                key = " vs ".join(sorted(races))
                pair_disparities[key].append(abs(va["score"] - vb["score"]))

    for key in sorted(pair_disparities.keys(),
                       key=lambda k: np.mean(pair_disparities[k]), reverse=True):
        a = np.array(pair_disparities[key])
        print(f"  {key:<30}  mean={np.mean(a):.5f}  std={np.std(a):.5f}  n={len(a)}")

    import csv
    output_path = os.path.join(os.path.dirname(__file__), args.output_csv)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "name", "race", "gender", "pronouns", "score"])
        for v in variants:
            writer.writerow([
                v["index"],
                v["identity"]["name"],
                v["identity"]["race_coding"],
                v["identity"]["gender"],
                v["identity"]["pronouns"],
                v["score"],
            ])
    print(f"\n  Scores saved to {output_path}")
    print(f"\n{'─'*70}")
    print("INTERPRETATION")
    print(f"{'─'*70}")
    max_race_spread = max(np.mean(race_groups[r]) for r in races_sorted) - \
                      min(np.mean(race_groups[r]) for r in races_sorted)
    if max_race_spread < 0.001:
        print(f"  Race score spread ({max_race_spread:.8f}) is negligible.")
        print(f"  Name-only mutations produce near-identical screener scores.")
        print(f"  The screener is effectively blind to race-coded names.")
        print(f"")
        print(f"  To amplify bias signal, add richer identity mutations:")
        print(f"    - Inject identity-signaling summary sentences")
        print(f"    - Use LLM to rewrite resume tone/style by identity")
        print(f"    - Add demographic-tagged achievements/affiliations")
    else:
        print(f"  Race score spread ({max_race_spread:.5f}) is {('meaningful' if max_race_spread > 0.01 else 'small but detectable')}.")
        print(f"  The screener shows differential treatment by race-coded name.")
    print(f"{'─'*70}")
    print("** p < 0.01, * p < 0.05, ns = not significant")
    print("Cohen's d: 0.2=small, 0.5=medium, 0.8=large")


if __name__ == "__main__":
    main()
