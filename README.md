# FairHire

Deterministic **Resume–JD matching** — NER-style parsing, rule-based scoring,
and a visual map of connecting lines between overlapping terms. Scoring and
matching are **always deterministic**; an optional DeepSeek extraction layer
only decides *what to look for* (soft skills, degrees, years) and never decides
*whether a match exists*.

## Layout

- `frontend/` — Next.js UI. Job description on the left, resume on the right.
  Toggle "Show connecting lines" to draw an SVG line from every matched JD term
  to the sentence/word it hits in the resume.
- `backend/` — FastAPI. Pipeline:

  ```
  parse (regex + curated ontology)                       -> parse_job_description / parse_resume
  extract (optional DeepSeek: requirements + evidence)   -> llm_extract.py   [hybrid mode]
  match  (exact / contextual / family / fuzzy)           -> matcher.py / hybrid.py
  score  (weighted, explainable dimensions)              -> score.py
  ```

## Modes

| Mode | When | Requirements extracted from JD |
| ---- | ---- | ------------------------------- |
| `deterministic` | no `FAIRHIRE_DEEPSEEK_KEY` | only named technologies from the curated ontology |
| `hybrid` | DeepSeek key configured | skills + soft skills + degrees + years + generic abilities |

For JDs that are mostly soft (e.g. "Bachelor's in CS, analytical skills,
develop and maintain software"), deterministic-only mode finds few or zero
terms. Set a DeepSeek key to lift those requirements out of the JD and match
them deterministically against the resume (degree regex, soft-skill evidence,
years comparison, token overlap).

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # add your FAIRHIRE_DEEPSEEK_KEY (optional)
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Optional env vars:

- `FAIRHIRE_DEEPSEEK_URL=https://api.deepseek.com`
- `FAIRHIRE_DEEPSEEK_KEY=sk-...`
- `FAIRHIRE_DEEPSEEK_MODEL=deepseek-chat`

CLI:

```bash
python fit_resume.py resume.pdf --jd job.txt
python fit_resume.py resume.pdf --jd job.txt --json
```

## Backend pipeline

| Step | Where | What |
| ---- | ----- | ---- |
| Structured fields | `fairhire/fitness/ner.py` | regex rules for email, phone, dates, URLs, degrees |
| Sections | `fairhire/fitness/sections.py` | summary / experience / projects / publications / skills / education |
| Skill tagging | `fairhire/fitness/ontology.py` | ~150 curated terms (languages, frameworks, DBs, cloud, ML) tagged with exact char offsets |
| LLM extraction | `fairhire/fitness/llm_extract.py` | optional DeepSeek: structured JD requirements + resume evidence |
| Matching | `fairhire/fitness/matcher.py` + `hybrid.py` | deterministic tiers: **exact** → **contextual** → **family** (SQL ⇒ PostgreSQL) → **fuzzy**; hybrid matches soft/degree/years/ability requirements |
| Scoring | `fairhire/fitness/score.py` | Required (0.55) + nice-to-have (0.10) + structure (0.15) + experience depth (0.20) |

Tests (no pytest needed):

```bash
python test_fitness.py
```

## Frontend

```bash
cd frontend
bun install   # or npm install
bun dev       # http://localhost:3000
```

Optional: `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`

## Product note

Scoring and matching are fully deterministic and explainable — every point
traces back to a concrete rule, and every visual link is a real matched
requirement with a quality label (`exact`, `contextual`, `family`, `near`).
Required vs nice-to-have terms are decided by where they appear in the JD
(requirements/responsibilities zone vs bonus/preferred zone). Not a vendor ATS
simulator.

The legacy bias-audit modules (`fairhire/stage*`, `fairhire/identity`) are
kept but are not part of this product path.
