import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

from fairhire.config import Config
from fairhire.stage1.name_pools import (
    NAME_POOLS,
    RACE_CODING,
    GENDER_CODING,
    PRONOUNS,
)

SYSTEM_PROMPT = """You are a resume anonymization tool. Your task is to rewrite only the identity-signaling parts of a resume: the name, pronouns, and any race/gender-coded language (e.g., member of "Black Engineers Association", "Women in Tech" affiliations, gender-coded adjectives like "nurturing" vs "assertive"). 

CRITICAL RULES:
1. Replace ONLY the name with the target name provided.
2. Replace pronouns to match the target gender expression.
3. Remove or neutralize any identity-signaling organizational affiliations, replacing them with neutral equivalents (e.g., "Society of Women Engineers" -> "Engineering Professional Society").
4. Strip gender-coded adjectives: replace with neutral equivalents.
5. DO NOT change: skills, years of experience, technical abilities, job titles, companies, education institutions, degrees, certifications, metrics (% increases), project descriptions, or responsibilities.
6. Return ONLY the rewritten resume text. No preamble, no explanation."""


def _sample_identity(exclude_category: str | None = None) -> dict[str, str]:
    categories = list(NAME_POOLS.keys())
    if exclude_category and exclude_category in categories:
        categories.remove(exclude_category)
    chosen_category = random.choice(categories)
    name = random.choice(NAME_POOLS[chosen_category])
    race = RACE_CODING[chosen_category]
    gender = GENDER_CODING[chosen_category]
    pronouns = PRONOUNS[gender]
    return {
        "name": name,
        "race_coding": race,
        "gender": gender,
        "pronouns": pronouns,
        "category": chosen_category,
    }


def _sample_pair_identities() -> tuple[dict[str, str], dict[str, str]]:
    id_a = _sample_identity()
    id_b = _sample_identity(exclude_category=id_a["category"])
    return id_a, id_b


def _clean_resume_text(text: str) -> str:
    if text.startswith("Here's a professional resume for"):
        lines = text.split("\n", 1)
        if len(lines) > 1:
            text = lines[1].strip()
    return text


def _generate_mutated_resume(
    client: OpenAI,
    original_resume: str,
    target_identity: dict,
    config: Config,
) -> str:
    cleaned = _clean_resume_text(original_resume)
    user_prompt = f"""Target identity:
Name: {target_identity['name']}
Pronouns: {target_identity['pronouns']}

Resume to rewrite:
{cleaned}"""

    response = client.chat.completions.create(
        model=config.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=config.llm_temperature,
        max_tokens=4096,
    )
    return response.choices[0].message.content.strip()


def _build_pair(
    client: OpenAI,
    row: pd.Series,
    config: Config,
) -> dict[str, Any] | None:
    try:
        identity_a, identity_b = _sample_pair_identities()
        resume_a = _generate_mutated_resume(client, row["Resume"], identity_a, config)
        resume_b = _generate_mutated_resume(client, row["Resume"], identity_b, config)
        return {
            "pair_id": str(uuid.uuid4()),
            "resume_A": resume_a,
            "resume_B": resume_b,
            "identity_A": {
                "name": identity_a["name"],
                "race_coding": identity_a["race_coding"],
                "gender": identity_a["gender"],
                "pronouns": identity_a["pronouns"],
            },
            "identity_B": {
                "name": identity_b["name"],
                "race_coding": identity_b["race_coding"],
                "gender": identity_b["gender"],
                "pronouns": identity_b["pronouns"],
            },
            "role": row["Role"],
            "job_description": row["Job_Description"],
            "original_resume_id": row["ID"],
        }
    except Exception as e:
        print(f"Error generating pair for {row['ID']}: {e}")
        return None


def generate_counterfactual_pairs(
    df: pd.DataFrame,
    config: Config,
) -> list[dict[str, Any]]:
    if not config.llm_api_key:
        raise ValueError(
            "FAIRHIRE_LLM_KEY not set. "
            "Set it via: export FAIRHIRE_LLM_KEY=your-key"
        )

    client = OpenAI(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
    )

    print(f"Checking LLM connectivity: {config.llm_base_url} model={config.llm_model}...")
    try:
        test_resp = client.chat.completions.create(
            model=config.llm_model,
            messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
            max_tokens=5,
            timeout=30,
        )
        print(f"LLM OK: {test_resp.choices[0].message.content.strip()}")
    except Exception as e:
        raise RuntimeError(f"Failed to reach LLM at {config.llm_base_url}: {e}")

    if config.subset_size > 0:
        df = df.sample(n=min(config.subset_size, len(df)), random_state=config.seed)

    pairs = []
    f = open(config.pairs_output_path, "w")
    try:
        with ThreadPoolExecutor(max_workers=config.llm_max_concurrency) as executor:
            futures = {
                executor.submit(_build_pair, client, row, config): row["ID"]
                for _, row in df.iterrows()
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Generating counterfactual pairs",
            ):
                result = future.result()
                if result:
                    pairs.append(result)
                    f.write(json.dumps(result) + "\n")
                    f.flush()
    finally:
        f.close()

    print(f"Generated {len(pairs)} pairs -> {config.pairs_output_path}")
    return pairs
