import json
import os
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from fairhire.config import Config

matplotlib.use("Agg")


BLUE = "#2563EB"
ORANGE = "#F59E0B"
GREEN = "#10B981"
RED = "#EF4444"
PURPLE = "#8B5CF6"
BG = "#F8FAFC"


def _set_style():
    sns.set_style("whitegrid")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "axes.titlesize": 14,
        "axes.titleweight": "semibold",
        "axes.labelsize": 12,
        "figure.facecolor": BG,
        "axes.facecolor": BG,
    })


def _load_disparities(config: Config) -> pd.DataFrame:
    records = []
    with open(config.disparities_output_path, "r") as f:
        for line in f:
            records.append(json.loads(line))
    df = pd.DataFrame(records)
    df["race_A"] = df["identity_A"].apply(lambda x: x["race_coding"])
    df["race_B"] = df["identity_B"].apply(lambda x: x["race_coding"])
    df["gender_A"] = df["identity_A"].apply(lambda x: x["gender"])
    df["gender_B"] = df["identity_B"].apply(lambda x: x["gender"])
    return df


def plot_disparity_distribution(df: pd.DataFrame, config: Config):
    _set_style()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.hist(df["disparity_score"], bins=50, color=BLUE, alpha=0.85, edgecolor="white")
    ax.axvline(df["disparity_score"].mean(), color=RED, linestyle="--", linewidth=2,
               label=f"Mean: {df['disparity_score'].mean():.4f}")
    ax.set_xlabel("Disparity Score (|fit_A - fit_B|)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Disparity Scores")
    ax.legend()

    ax = axes[1]
    ax.hist(df["disparity_direction"], bins=50, color=ORANGE, alpha=0.85, edgecolor="white")
    ax.axvline(0, color="black", linestyle="-", linewidth=1)
    ax.axvline(df["disparity_direction"].mean(), color=RED, linestyle="--", linewidth=2,
               label=f"Mean: {df['disparity_direction'].mean():.4f}")
    ax.set_xlabel("Disparity Direction (fit_A - fit_B)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Disparity Direction (Signed)")
    ax.legend()

    plt.tight_layout()
    path = os.path.join(config.viz_output_dir, "disparity_distribution.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_race_gender_heatmap(df: pd.DataFrame, config: Config):
    _set_style()

    pairs = []
    for _, row in df.iterrows():
        pair_key = tuple(sorted([row["race_A"], row["race_B"]]))
        pair_key_rev = tuple(sorted([row["race_B"], row["race_A"]]))
        pairs.append({
            "race_pair": f"{row['race_A']} vs {row['race_B']}",
            "disparity": row["disparity_score"],
        })

    pair_df = pd.DataFrame(pairs)
    race_pair_means = pair_df.groupby("race_pair")["disparity"].mean().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = [BLUE] * len(race_pair_means)
    bars = ax.bar(range(len(race_pair_means)), race_pair_means.values, color=colors, alpha=0.85, edgecolor="white")
    ax.set_xticks(range(len(race_pair_means)))
    ax.set_xticklabels(race_pair_means.index, rotation=45, ha="right")
    ax.set_ylabel("Mean Disparity Score")
    ax.set_title("Mean Disparity by Race Pairing")
    ax.axhline(df["disparity_score"].mean(), color=RED, linestyle="--",
               label=f"Overall mean: {df['disparity_score'].mean():.4f}")
    ax.legend()

    plt.tight_layout()
    path = os.path.join(config.viz_output_dir, "race_disparity_bars.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_score_scatter(df: pd.DataFrame, config: Config):
    _set_style()
    fig, ax = plt.subplots(figsize=(8, 8))

    ax.scatter(
        df["fit_score_A"], df["fit_score_B"],
        c=df["disparity_score"], cmap="YlOrRd",
        alpha=0.5, s=10, edgecolors="none",
    )

    lim_min = min(df["fit_score_A"].min(), df["fit_score_B"].min())
    lim_max = max(df["fit_score_A"].max(), df["fit_score_B"].max())
    ax.plot([lim_min, lim_max], [lim_min, lim_max], "k--", alpha=0.5, label="y = x (no disparity)")
    ax.set_xlim(lim_min, lim_max)
    ax.set_ylim(lim_min, lim_max)
    ax.set_xlabel("Fit Score A")
    ax.set_ylabel("Fit Score B")
    ax.set_title("Fit Score Comparison: Resume A vs Resume B")
    ax.legend()

    cbar = plt.colorbar(ax.collections[0], ax=ax)
    cbar.set_label("Disparity")

    plt.tight_layout()
    path = os.path.join(config.viz_output_dir, "score_scatter.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_gender_disparity(df: pd.DataFrame, config: Config):
    _set_style()

    gender_data = []
    for _, row in df.iterrows():
        gender_data.append({
            "gender_A": row["gender_A"],
            "mean_fit": row["fit_score_A"],
        })
        gender_data.append({
            "gender_B": row["gender_B"],
            "mean_fit": row["fit_score_B"],
        })

    gdf = pd.DataFrame(gender_data)
    gender_means = gdf.groupby("gender_A")["mean_fit"].agg(["mean", "std"])

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [BLUE, ORANGE, GREEN]
    bars = ax.bar(
        range(len(gender_means)),
        gender_means["mean"],
        yerr=gender_means["std"],
        color=colors[:len(gender_means)],
        alpha=0.85,
        edgecolor="white",
        capsize=5,
    )
    ax.set_xticks(range(len(gender_means)))
    ax.set_xticklabels(gender_means.index)
    ax.set_ylabel("Mean Fit Score")
    ax.set_title("Mean Fit Score by Gender")

    for bar, mean_val in zip(bars, gender_means["mean"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.001,
                f"{mean_val:.4f}", ha="center", fontsize=10)

    plt.tight_layout()
    path = os.path.join(config.viz_output_dir, "gender_disparity.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def plot_race_disparity(df: pd.DataFrame, config: Config):
    _set_style()

    race_data = []
    for _, row in df.iterrows():
        race_data.append({"race": row["race_A"], "mean_fit": row["fit_score_A"]})
        race_data.append({"race": row["race_B"], "mean_fit": row["fit_score_B"]})

    rdf = pd.DataFrame(race_data)
    race_means = rdf.groupby("race")["mean_fit"].agg(["mean", "std"]).sort_values("mean", ascending=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [BLUE, ORANGE, GREEN, PURPLE, RED]
    bars = ax.bar(
        range(len(race_means)),
        race_means["mean"],
        yerr=race_means["std"],
        color=colors[:len(race_means)],
        alpha=0.85,
        edgecolor="white",
        capsize=5,
    )
    ax.set_xticks(range(len(race_means)))
    ax.set_xticklabels(race_means.index)
    ax.set_ylabel("Mean Fit Score")
    ax.set_title("Mean Fit Score by Race")

    for bar, mean_val in zip(bars, race_means["mean"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.001,
                f"{mean_val:.4f}", ha="center", fontsize=10)

    plt.tight_layout()
    path = os.path.join(config.viz_output_dir, "race_disparity.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def generate_all_plots(config: Config):
    os.makedirs(config.viz_output_dir, exist_ok=True)
    df = _load_disparities(config)
    plot_disparity_distribution(df, config)
    plot_score_scatter(df, config)
    plot_gender_disparity(df, config)
    plot_race_disparity(df, config)
    plot_race_gender_heatmap(df, config)
    print(f"All plots saved to {config.viz_output_dir}/")
