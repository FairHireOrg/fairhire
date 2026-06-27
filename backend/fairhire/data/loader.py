import pandas as pd
from fairhire.config import Config


def load_dataset(config: Config) -> pd.DataFrame:
    df = pd.read_csv(config.dataset_path)
    df = normalize_roles(df)
    return df


def normalize_roles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Role"] = df["Role"].str.strip().str.lower()
    return df
