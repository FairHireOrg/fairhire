"""Optional DeepSeek-assisted extraction (hybrid mode).

The LLM only performs *extraction* of structured requirements from the JD and
structured evidence from the resume — the fuzzy parts a curated ontology can't
cover (soft skills, degrees, years of experience, generic abilities). Every
subsequent match and every score stays deterministic and explainable.

When no API key is configured, this module is never used and the system runs
purely deterministic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from fairhire.config import Config

KINDS = ("skill", "degree", "years", "soft", "ability")


@dataclass
class Requirement:
    text: str
    kind: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "kind": self.kind, "required": self.required}


@dataclass
class ResumeEvidence:
    degree: str = ""
    skills: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    total_years: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "degree": self.degree,
            "skills": self.skills,
            "soft_skills": self.soft_skills,
            "strengths": self.strengths,
            "total_years": self.total_years,
            "summary": self.summary,
        }


JD_SYSTEM = """You extract the hiring requirements from a job description into strict JSON.

Classify every requirement into exactly one kind:
- "skill": a specific technology, language, framework, tool, or platform
- "degree": an education requirement (e.g. "Bachelor's degree in Computer Science")
- "years": a years-of-experience requirement (e.g. "5+ years of software engineering")
- "soft": a soft skill or personal attribute (e.g. analytical, problem-solving, communication)
- "ability": a general capability or responsibility that is required (e.g. "develop and maintain
  internal software applications", "troubleshoot software bugs")

Rules:
- Extract the REAL requirement text from the JD; never invent requirements.
- Split compound requirements into separate items (one skill or idea each).
- requirements = must-have / essential items. nice_to_haves = bonus, preferred, or "plus" items.
- Ignore benefits, salary, compensation, company culture, legal boilerplate (E-Verify, sponsorship), and perks.
- If a term appears only as a technology mention without being a requirement, leave it out.
- Return ONLY JSON, no prose."""

RESUME_SYSTEM = """You extract grounded evidence from a resume into strict JSON.

Return:
- degree: the highest degree as written (e.g. "B.S. Computer Science"); empty string if none.
- skills: concrete technologies/tools clearly present (languages, frameworks, platforms).
- soft_skills: soft skills or attributes that are actually evidenced (e.g. teaching, leadership,
  reverse-engineering, attention to detail) — grounded, not generic.
- strengths: 3-6 substantive accomplishments evidenced in the text, each short.
- total_years: total years of relevant professional experience (number) — estimate conservatively
  from the date ranges; 0 if not derivable.
- summary: one sentence factual summary of the candidate.

Rules:
- NEVER invent employers, degrees, titles, dates, or skills.
- Return ONLY JSON, no prose."""


def _client(config: Config) -> OpenAI:
    return OpenAI(base_url=config.deepseek_base_url, api_key=config.deepseek_api_key)


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Last valid top-level {...} block wins (models may emit reasoning first).
    depth = 0
    start = None
    candidates: list[str] = []
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start : i + 1])
                    start = None
    for blob in reversed(candidates):
        try:
            data = json.loads(blob)
            if isinstance(data, dict) and data:
                return data
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("no json object found", text, 0)


def _chat_json(
    *,
    system: str,
    user: str,
    config: Config,
    max_tokens: int = 1500,
    attempts: int = 2,
) -> dict[str, Any]:
    client = _client(config)
    last_err: Exception | None = None
    for attempt in range(attempts):
        messages: Any = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": user
                + "\n\nReturn ONLY a single JSON object. No markdown, no analysis.",
            },
        ]
        try:
            resp = client.chat.completions.create(
                model=config.deepseek_model,
                messages=messages,
                temperature=0.1 if attempt == 0 else 0.0,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return _extract_json(content)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(f"DeepSeek extraction failed: {last_err}")


def _str_list(value: Any, limit: int = 16) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = str(item).strip().strip("•-*")
        if s and len(s) >= 2 and s not in out:
            out.append(s[:140])
        if len(out) >= limit:
            break
    return out


def _valid_kind(value: Any) -> str:
    k = str(value or "").lower().strip()
    return k if k in KINDS else "ability"


def extract_requirements(jd_text: str, config: Config | None = None) -> list[Requirement] | None:
    config = config or Config()
    if not config.llm_extraction_enabled:
        return None
    try:
        data = _chat_json(
            system=JD_SYSTEM,
            user=(
                "Job description:\n\n"
                f"{jd_text[:6000]}\n\n"
                'Return JSON: {"requirements":[{"text":"...","kind":"skill|degree|years|soft|ability"}],'
                '"nice_to_haves":[{"text":"...","kind":"..."}]}'
            ),
            config=config,
            max_tokens=2200,
        )
    except Exception:  # noqa: BLE001
        return None

    requirements: list[Requirement] = []
    for raw in data.get("requirements") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if len(text) < 2:
            continue
        requirements.append(Requirement(text=text, kind=_valid_kind(raw.get("kind"))))
    for raw in data.get("nice_to_haves") or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if len(text) < 2:
            continue
        requirements.append(Requirement(text=text, kind=_valid_kind(raw.get("kind")), required=False))
    return requirements


def extract_resume_evidence(resume_text: str, config: Config | None = None) -> ResumeEvidence | None:
    config = config or Config()
    if not config.llm_extraction_enabled:
        return None
    try:
        data = _chat_json(
            system=RESUME_SYSTEM,
            user=(
                "Resume:\n\n"
                f"{resume_text[:7000]}\n\n"
                'Return JSON: {"degree":"...","skills":["..."],"soft_skills":["..."],'
                '"strengths":["..."],"total_years":0,"summary":"..."}'
            ),
            config=config,
            max_tokens=1800,
        )
    except Exception:  # noqa: BLE001
        return None

    years = 0.0
    try:
        years = float(data.get("total_years") or 0)
    except (TypeError, ValueError):
        years = 0.0

    return ResumeEvidence(
        degree=str(data.get("degree") or "").strip(),
        skills=_str_list(data.get("skills")),
        soft_skills=_str_list(data.get("soft_skills"), 12),
        strengths=_str_list(data.get("strengths"), 6),
        total_years=years,
        summary=str(data.get("summary") or "")[:300],
    )
