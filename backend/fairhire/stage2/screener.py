import json
import os
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from fairhire.config import Config


class ContrastiveDataset(Dataset):
    def __init__(self, pairs: list[dict], embedder: SentenceTransformer, config: Config):
        self.config = config
        self.pairs = pairs

        self.resume_texts: list[str] = []
        self.job_texts: list[str] = []
        self.role_labels: list[str] = []
        for p in pairs:
            self.resume_texts.append(p["resume_A"])
            self.resume_texts.append(p["resume_B"])
            self.job_texts.append(p["job_description"])
            self.job_texts.append(p["job_description"])
            self.role_labels.append(p["role"])
            self.role_labels.append(p["role"])

        print("Encoding resumes...")
        self.resume_embeddings = embedder.encode(
            self.resume_texts,
            batch_size=config.batch_size,
            show_progress_bar=True,
            convert_to_tensor=True,
        )
        print("Encoding job descriptions...")
        unique_jobs = list(dict.fromkeys(self.job_texts))
        job_map = embedder.encode(
            unique_jobs,
            batch_size=config.batch_size,
            show_progress_bar=True,
            convert_to_tensor=True,
        )
        self.job_embeddings = torch.stack([job_map[unique_jobs.index(j)] for j in self.job_texts])

        role_to_idx = {r: i for i, r in enumerate(sorted(set(self.role_labels)))}
        self.role_ids = torch.tensor([role_to_idx[r] for r in self.role_labels])

    def __len__(self):
        return len(self.resume_texts)

    def __getitem__(self, idx):
        return self.resume_embeddings[idx], self.job_embeddings[idx], self.role_ids[idx]


def load_pairs_for_training(config: Config) -> list[dict]:
    if not os.path.exists(config.pairs_output_path):
        raise FileNotFoundError(
            f"Pairs file not found: {config.pairs_output_path}\n"
            "Run Stage 1 first: python run_pipeline.py --stage 1"
        )
    pairs = []
    with open(config.pairs_output_path, "r") as f:
        for line in f:
            pairs.append(json.loads(line))
    if not pairs:
        raise RuntimeError(
            f"Pairs file is empty: {config.pairs_output_path}\n"
            "Run Stage 1 first: python run_pipeline.py --stage 1"
        )
    return pairs


class Screener(nn.Module):
    def __init__(self, embedding_dim: int = 768):
        super().__init__()
        self.linear = nn.Linear(embedding_dim, 1)

    def forward(self, resume_emb: torch.Tensor, job_emb: torch.Tensor) -> torch.Tensor:
        d_k = resume_emb.size(-1)
        attn_scores = (resume_emb * job_emb).sum(dim=-1, keepdim=True) / np.sqrt(d_k)
        attn_weights = F.softmax(attn_scores, dim=0)
        scored = attn_weights * resume_emb
        logits = self.linear(scored)
        return torch.sigmoid(logits).squeeze(-1)


class TokenLevelScreener(nn.Module):
    def __init__(self, embedding_dim: int = 768):
        super().__init__()
        self.linear = nn.Linear(embedding_dim, 1)

    def forward(
        self,
        resume_token_emb: torch.Tensor,
        job_pooled_emb: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        d_k = resume_token_emb.size(-1)
        scores = torch.bmm(
            resume_token_emb,
            job_pooled_emb.unsqueeze(-1),
        ) / np.sqrt(d_k)
        scores = scores.squeeze(-1)
        scores = scores.masked_fill(attention_mask == 0, -1e9)
        attn_weights = F.softmax(scores, dim=1)
        scored = (attn_weights.unsqueeze(-1) * resume_token_emb).sum(dim=1)
        logits = self.linear(scored)
        return torch.sigmoid(logits).squeeze(-1)


def contrastive_loss(
    scores: torch.Tensor,
    role_ids: torch.Tensor,
    margin: float = 0.5,
) -> torch.Tensor:
    n = scores.size(0)
    loss = 0.0
    count = 0
    for i in range(n):
        same_role = (role_ids == role_ids[i]) & (torch.arange(n) != i)
        diff_role = role_ids != role_ids[i]
        if same_role.any() and diff_role.any():
            pos = scores[same_role].mean()
            neg = scores[diff_role].mean()
            loss += F.relu(margin - pos + neg)
            count += 1
    return loss / max(count, 1)


def train_screener(
    pairs: list[dict],
    config: Config,
) -> Screener:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    print(f"Loading embedding model: {config.embedding_model}")

    embedder = SentenceTransformer(config.embedding_model, device=device)

    dataset = ContrastiveDataset(pairs, embedder, config)
    dataloader = DataLoader(
        dataset,
        batch_size=config.batch_size * 2,
        shuffle=True,
    )

    model = Screener(embedding_dim=config.embedding_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

    model.train()
    for epoch in range(config.num_epochs):
        epoch_loss = 0.0
        epoch_batches = 0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch + 1}/{config.num_epochs}")
        for resume_emb, job_emb, role_ids in pbar:
            resume_emb = resume_emb.to(device)
            job_emb = job_emb.to(device)
            role_ids = role_ids.to(device)

            scores = model(resume_emb, job_emb)
            loss = contrastive_loss(scores, role_ids, config.contrastive_margin)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            epoch_batches += 1
            pbar.set_postfix({"loss": f"{loss.item():.4f}"})

        avg_loss = epoch_loss / max(epoch_batches, 1)
        print(f"Epoch {epoch + 1} avg loss: {avg_loss:.4f}")

    torch.save(model.state_dict(), config.model_output_path)
    print(f"Model saved to {config.model_output_path}")
    return model
