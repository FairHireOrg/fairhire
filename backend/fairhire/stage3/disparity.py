import json
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from fairhire.config import Config
from fairhire.stage2.screener import Screener


def _changed_dimensions(id_a: dict, id_b: dict) -> list[str]:
    dims = []
    if id_a.get("race_coding") != id_b.get("race_coding"):
        dims.append("race_coding")
    if id_a.get("gender") != id_b.get("gender"):
        dims.append("gender")
    if id_a.get("name") != id_b.get("name"):
        dims.append("name")
    return dims


def measure_disparities(
    pairs: list[dict],
    model: Screener,
    embedder: SentenceTransformer,
    config: Config,
) -> list[dict[str, Any]]:
    device = next(model.parameters()).device
    model.eval()

    disparities = []

    for pair in tqdm(pairs, desc="Measuring disparities"):
        resume_a = pair["resume_A"]
        resume_b = pair["resume_B"]
        job_desc = pair["job_description"]

        emb_a = embedder.encode(
            [resume_a],
            convert_to_tensor=True,
            show_progress_bar=False,
        ).to(device)
        emb_b = embedder.encode(
            [resume_b],
            convert_to_tensor=True,
            show_progress_bar=False,
        ).to(device)
        emb_job = embedder.encode(
            [job_desc],
            convert_to_tensor=True,
            show_progress_bar=False,
        ).to(device)

        with torch.no_grad():
            score_a = model(emb_a, emb_job).item()
            score_b = model(emb_b, emb_job).item()

        disparity_score = abs(score_a - score_b)
        disparity_direction = score_a - score_b

        changed = _changed_dimensions(pair["identity_A"], pair["identity_B"])

        disparities.append({
            "pair_id": pair["pair_id"],
            "fit_score_A": round(score_a, 6),
            "fit_score_B": round(score_b, 6),
            "disparity_score": round(disparity_score, 6),
            "disparity_direction": round(disparity_direction, 6),
            "changed_dimensions": changed,
            "identity_A": pair["identity_A"],
            "identity_B": pair["identity_B"],
            "role": pair["role"],
        })

    with open(config.disparities_output_path, "w") as f:
        for d in disparities:
            f.write(json.dumps(d) + "\n")

    print(f"Measured {len(disparities)} disparities -> {config.disparities_output_path}")

    scores = [d["disparity_score"] for d in disparities]
    print(f"Disparity stats: mean={np.mean(scores):.4f}, median={np.median(scores):.4f}, "
          f"max={np.max(scores):.4f}, min={np.min(scores):.4f}")

    return disparities
