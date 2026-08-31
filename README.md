# FairHire

Deterministic **Resume–JD matching** — NER-style parsing, rule-based scoring,
and a visual map of connecting lines between overlapping terms. The **score** is
always computed by fixed rules over confirmed matches. An optional DeepSeek layer
handles the semantic work a curated ontology can't: extracting requirements and
*turning what a resume didn't spell out into a questionnaire* — e.g. a resume
with "TypeScript" gets a *suggest* for the "JavaScript" requirement, and you
confirm it. The LLM only suggests whether something is satisfied; it never sets
the grade, so the same inputs and answers always yield the same score.

## Layout

- `frontend/` — Next.js UI. Job description on the left, resume on the right.
  Toggle "Show connecting lines" to draw an SVG line from every matched JD term
  to the sentence/word it hits in the resume.
- `backend/` — FastAPI. Pipeline:

  ```
  parse  (regex + curated ontology)                      -> parse_job_description / parse_resume
  extract(optional DeepSeek: requirements + evidence)    -> llm_extract.py      [hybrid mode]
   match (exact / contextual / family) lexical, then     -> matcher.py / hybrid.py
          LLM-suggested confirm list for the rest        -> llm_extract.py::judge_requirements
  score  (weighted, explainable dimensions)              -> score.py
  ```

## Modes

| Mode | When | Matching |
| ---- | ---- | -------- |
| `deterministic` | no `FAIRHIRE_DEEPSEEK_KEY` | lexical only (exact / contains / family) |
| `hybrid` | DeepSeek key configured | lexical tiers + LLM-suggested questionnaire (you confirm super-sets, synonyms, novel skills) |

The LLM never assigns a score — it only *suggests* whether a requirement is
satisfied (with a quoted resume span as evidence), and those suggestions become a
questionnaire. Scoring stays a fixed rule over confirmed matches, so the same
inputs and answers yield the same grade and candidates are not graded
arbitrarily.

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
| Matching | `fairhire/fitness/matcher.py` + `hybrid.py` | lexical tiers: **exact** → **contextual** → **family** (SQL ⇒ PostgreSQL); then, in hybrid mode, the LLM only *suggests* the leftover requirements (`judge_requirements`) as a confirm list for the user |
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
