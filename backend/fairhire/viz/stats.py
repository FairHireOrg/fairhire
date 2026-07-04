import json
from typing import Any

import numpy as np
from scipy import stats

from fairhire.config import Config


def _load_disparities(config: Config) -> list[dict[str, Any]]:
    records = []
    with open(config.disparities_output_path, "r") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    s1, s2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return float((np.mean(group1) - np.mean(group2)) / pooled_std)


def run_stats(config: Config) -> None:
    records = _load_disparities(config)

    race_scores: dict[str, list[float]] = {}
    gender_scores: dict[str, list[float]] = {}
    race_pair_disparities: dict[str, list[float]] = {}
    gender_pair_disparities: dict[str, list[float]] = {}

    for r in records:
        for side in ("A", "B"):
            identity = r[f"identity_{side}"]
            race = identity["race_coding"]
            gender = identity["gender"]
            score = r[f"fit_score_{side}"]
            race_scores.setdefault(race, []).append(score)
            gender_scores.setdefault(gender, []).append(score)

        races = frozenset((r["identity_A"]["race_coding"], r["identity_B"]["race_coding"]))
        if len(races) > 1:
            key = " vs ".join(sorted(races))
            race_pair_disparities.setdefault(key, []).append(r["disparity_score"])

        genders = frozenset((r["identity_A"]["gender"], r["identity_B"]["gender"]))
        if len(genders) > 1:
            key = " vs ".join(sorted(genders))
            gender_pair_disparities.setdefault(key, []).append(r["disparity_score"])

    print()
    print("=" * 70)
    print("FAIRHIRE BIAS AUDIT — STATISTICAL REPORT")
    print("=" * 70)
    print(f"Total pairs analyzed: {len(records)}")
    print(f"Overall mean disparity: {np.mean([r['disparity_score'] for r in records]):.5f}")
    print(f"Overall median disparity: {np.median([r['disparity_score'] for r in records]):.5f}")

    races_present = sorted(race_scores.keys())
    if len(races_present) >= 2:
        print()
        print("-" * 70)
        print("RACE ANALYSIS — Fit Score by Race")
        print("-" * 70)
        all_race_scores = {r: np.array(v) for r, v in race_scores.items()}
        print(f"{'Race':<12} {'Count':>6} {'Mean Score':>10} {'Std':>8}")
        for race in races_present:
            a = all_race_scores[race]
            print(f"{race:<12} {len(a):>6} {np.mean(a):>10.5f} {np.std(a):>8.5f}")

        f_stat, p_race_anova = stats.f_oneway(*all_race_scores.values())
        print()
        print(f"One-way ANOVA: F={f_stat:.4f}, p={p_race_anova:.6f}")
        if p_race_anova < 0.05:
            print("  SIGNIFICANT — race has a detectable effect on fit scores")
        else:
            print("  NOT SIGNIFICANT — no detectable race effect on fit scores")

        print()
        print("Pairwise t-tests (race):")
        for i, r1 in enumerate(races_present):
            for r2 in races_present[i + 1:]:
                t_stat, p_val = stats.ttest_ind(all_race_scores[r1], all_race_scores[r2])
                d = _cohens_d(all_race_scores[r1], all_race_scores[r2])
                sig = "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
                print(f"  {r1:<10} vs {r2:<10}  t={t_stat:>7.3f}  p={p_val:.5f}  d={d:>6.3f}  [{sig}]")

    genders_present = sorted(gender_scores.keys())
    if len(genders_present) >= 2:
        print()
        print("-" * 70)
        print("GENDER ANALYSIS — Fit Score by Gender")
        print("-" * 70)
        all_gender_scores = {g: np.array(v) for g, v in gender_scores.items()}
        print(f"{'Gender':<12} {'Count':>6} {'Mean Score':>10} {'Std':>8}")
        for gender in genders_present:
            a = all_gender_scores[gender]
            print(f"{gender:<12} {len(a):>6} {np.mean(a):>10.5f} {np.std(a):>8.5f}")

        f_stat, p_gender_anova = stats.f_oneway(*all_gender_scores.values())
        print()
        print(f"One-way ANOVA: F={f_stat:.4f}, p={p_gender_anova:.6f}")
        if p_gender_anova < 0.05:
            print("  SIGNIFICANT")
        else:
            print("  NOT SIGNIFICANT")

        print()
        print("Pairwise t-tests (gender):")
        for i, g1 in enumerate(genders_present):
            for g2 in genders_present[i + 1:]:
                t_stat, p_val = stats.ttest_ind(all_gender_scores[g1], all_gender_scores[g2])
                d = _cohens_d(all_gender_scores[g1], all_gender_scores[g2])
                sig = "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
                print(f"  {g1:<10} vs {g2:<10}  t={t_stat:>7.3f}  p={p_val:.5f}  d={d:>6.3f}  [{sig}]")

    print()
    print("-" * 70)
    print("DISPARITY BY IDENTITY PAIRING")
    print("-" * 70)
    for key, vals in sorted(race_pair_disparities.items(), key=lambda x: -np.mean(x[1])):
        v = np.array(vals)
        print(f"  {key:<30}  mean={np.mean(v):.5f}  std={np.std(v):.5f}  n={len(v)}")

    print()
    print("-" * 70)
    print("DISPARITY BY GENDER PAIRING")
    print("-" * 70)
    for key, vals in sorted(gender_pair_disparities.items(), key=lambda x: -np.mean(x[1])):
        v = np.array(vals)
        print(f"  {key:<30}  mean={np.mean(v):.5f}  std={np.std(v):.5f}  n={len(v)}")

    print()
    print("=" * 70)
    print("** p < 0.01, * p < 0.05, ns = not significant")
    print("Cohen's d: 0.2=small, 0.5=medium, 0.8=large")
    print("=" * 70)
