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

    deepseek_api_key: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_max_concurrency: int = 10
    deepseek_temperature: float = 0.7

    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_dim: int = 768
    batch_size: int = 32
    learning_rate: float = 1e-4
    num_epochs: int = 10
    contrastive_margin: float = 0.5

    subset_size: int = 0

    seed: int = 42
