import os
from dataclasses import dataclass, field


@dataclass
class Config:
    dataset_path: str = os.path.join(os.path.dirname(__file__), "..", "dataset.csv")
    pairs_output_path: str = os.path.join(os.path.dirname(__file__), "..", "pairs.jsonl")
    disparities_output_path: str = os.path.join(
        os.path.dirname(__file__), "..", "disparities.jsonl"
    )
    model_output_path: str = os.path.join(os.path.dirname(__file__), "..", "screener_model.pt")
    viz_output_dir: str = os.path.join(os.path.dirname(__file__), "..", "plots")

    llm_base_url: str = field(
        default_factory=lambda: os.environ.get("FAIRHIRE_LLM_URL", "http://127.0.0.1:8888/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get(
            "FAIRHIRE_LLM_KEY", "sk-unsloth-8099bd1110cbf02bbfe2123f587a518f"
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get(
            "FAIRHIRE_LLM_MODEL", "unsloth/gemma-4-E4B-it-GGUF:UD-Q5_K_XL"
        )
    )
    llm_max_concurrency: int = 4
    llm_temperature: float = 0.7

    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_dim: int = 768
    batch_size: int = 32
    learning_rate: float = 1e-4
    num_epochs: int = 10
    contrastive_margin: float = 0.5

    subset_size: int = 100

    seed: int = 42
