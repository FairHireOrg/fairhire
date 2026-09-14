"""Config for FairHire.

Reads environment variables, then a `.env` file in this directory if present.
DeepSeek extraction is optional: scoring/matching is always deterministic, and
the LLM only supplies structured *requirements* when a key is configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _load_dotenv(path: str | None = None) -> None:
    """Minimal .env loader (no dependency). Does not override existing env."""
    candidates = [
        path,
        os.path.join(os.path.dirname(__file__), "..", ".env"),  # backend/.env
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),  # repo root
    ]
    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        with open(candidate, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        break


_load_dotenv()


@dataclass
class Config:
    dataset_path: str = os.path.join(os.path.dirname(__file__), "..", "dataset.csv")
    pairs_output_path: str = os.path.join(os.path.dirname(__file__), "..", "pairs.jsonl")
    disparities_output_path: str = os.path.join(
        os.path.dirname(__file__), "..", "disparities.jsonl"
    )
    model_output_path: str = os.path.join(os.path.dirname(__file__), "..", "screener_model.pt")
    viz_output_dir: str = os.path.join(os.path.dirname(__file__), "..", "plots")

    # Legacy local-Unsloth fields (used by the audit pipeline only).
    llm_base_url: str = field(
        default_factory=lambda: os.environ.get("FAIRHIRE_LLM_URL", "http://127.0.0.1:8888/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("FAIRHIRE_LLM_KEY", "sk-unsloth-90323bd6dc533ca996b876ecf4fdabc1")
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get(
            "FAIRHIRE_LLM_MODEL", "unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL"
        )
    )
    llm_max_concurrency: int = 4
    llm_temperature: float = 0.7

    # DeepSeek-assisted extraction (optional). Enables the hybrid mode.
    deepseek_base_url: str = field(
        default_factory=lambda: os.environ.get("FAIRHIRE_DEEPSEEK_URL", "https://api.deepseek.com")
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.environ.get("FAIRHIRE_DEEPSEEK_KEY", "").strip()
    )
    deepseek_model: str = field(
        default_factory=lambda: os.environ.get("FAIRHIRE_DEEPSEEK_MODEL", "deepseek-flash")
    )

    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_dim: int = 768
    batch_size: int = 32
    learning_rate: float = 1e-4
    num_epochs: int = 10
    contrastive_margin: float = 0.5

    subset_size: int = 100

    seed: int = 42

    @property
    def llm_extraction_enabled(self) -> bool:
        return bool(self.deepseek_api_key)
