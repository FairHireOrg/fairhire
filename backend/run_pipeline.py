import argparse
import random

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from fairhire.config import Config
from fairhire.data import load_dataset
from fairhire.stage1 import generate_counterfactual_pairs, generate_pairs_regex
from fairhire.stage2 import load_pairs_for_training, train_screener
from fairhire.stage2.screener import Screener
from fairhire.stage3 import measure_disparities
from fairhire.viz import generate_all_plots, run_stats


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main():
    parser = argparse.ArgumentParser(description="FairHire AI Bias Audit Pipeline")
    parser.add_argument("--stage", type=int, default=0, choices=[0, 1, 2, 3, 4, 5],
                        help="1=pairs, 2=train, 3=measure, 4=viz, 5=stats. 0=all.")
    parser.add_argument("--subset", type=int, default=None,
                        help="Number of records to process (default: 100). Use 0 for all.")
    parser.add_argument("--pairs-file", type=str, default=None,
                        help="Path to pre-generated pairs JSONL (skip stage 1)")
    parser.add_argument("--llm", action="store_true",
                        help="Use LLM for pair generation instead of regex (slow)")
    args = parser.parse_args()

    kwargs = {}
    if args.subset is not None:
        kwargs["subset_size"] = args.subset
    config = Config(**kwargs)
    if args.pairs_file:
        config.pairs_output_path = args.pairs_file
    set_seed(config.seed)

    print("=" * 60)
    print("FairHire AI — Bias Audit Platform")
    print("=" * 60)

    if args.stage in (0, 1):
        print("\n[Stage 1] Loading dataset & generating counterfactual pairs...")
        df = load_dataset(config)
        print(f"Loaded {len(df)} records across {df['Role'].nunique()} roles")
        if config.subset_size > 0:
            print(f"Subset mode: {config.subset_size} records")
        if args.llm:
            print("Using LLM-based generator")
            generate_counterfactual_pairs(df, config)
        else:
            print("Using regex-based generator")
            generate_pairs_regex(df, config)

    if args.stage in (0, 2):
        print("\n[Stage 2] Training attention-weighted screener...")
        pairs = load_pairs_for_training(config)
        print(f"Loaded {len(pairs)} pairs for training")
        train_screener(pairs, config)

    if args.stage in (0, 3):
        print("\n[Stage 3] Measuring disparities...")
        pairs = load_pairs_for_training(config)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        embedder = SentenceTransformer(config.embedding_model, device=device)
        model = Screener(embedding_dim=config.embedding_dim).to(device)
        model.load_state_dict(
            torch.load(config.model_output_path, map_location=device, weights_only=True)
        )
        measure_disparities(pairs, model, embedder, config)

    if args.stage in (0, 4):
        print("\n[Stage 4] Generating visualizations...")
        generate_all_plots(config)

    if args.stage in (0, 5) or args.stage == 5:
        print("\n[Stage 5] Running statistical analysis...")
        run_stats(config)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
