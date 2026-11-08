# FairHire

Deterministic **ATS-parsability** for resumes — NER-style parsing and rule-based
scoring of how cleanly a machine can read a document: contact block, standard
section headings, chronological roles, an education entry, keyword-rich skills
and scannable bullets. The **score is computed only from the resume** with exact
rules, so identical input always yields an identical score.

The job description is *optional* and is used only as a **relevance vector**: it
surfaces which of its concepts already appear in the resume (keyword relevance)
and never affects the score. The optional DeepSeek layer only feeds the
reviewed "suggest requirements" list; it is never on the scoring path and can
never decide a match or a grade.

## Layout

- `frontend/` — Next.js UI. Paste or upload a resume for an ATS score; add a job
  description if you also want keyword relevance.
- `backend/` — FastAPI. Pipeline:

  ```
  parse  (regex + curated ontology)                      -> parse_resume / parse_job_description
  evaluate(ATS parsability, resume-only)                 -> ats.py
  vector (JD -> keyword relevance, informational)        -> requirements.py + hybrid.py
  ```
  ```

## Scoring

The ATS score is **resume-only and deterministic**. Every dimension is a fixed
rule over what the parser can extract, so identical input always yields an
identical score. The job description is optional; if present it only surfaces
keyword relevance and never affects the score.

The optional DeepSeek layer feeds a reviewed "suggest requirements" list for the
JD vector; it is never on the scoring path and cannot decide a match or a grade.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # add your FAIRHIRE_DEEPSEEK_KEY (optional)
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

To host it on PythonAnywhere, see [docs/deploy-pythonanywhere.md](docs/deploy-pythonanywhere.md).

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
| ATS evaluation | `fairhire/fitness/ats.py` | resume-only, deterministic: contact, sections, chronology, education, keywords, bullets, text extraction |
| JD vector | `fairhire/fitness/requirements.py` + `hybrid.py` | optional keyword relevance from the job description (informational, never scored) |
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

Scoring is fully deterministic and explainable — every point traces back to a
concrete rule over what the parser extracts. The score measures ATS parsability
of the resume only; it is not a hiring probability, a measure of ability, or a
verdict on bias. The job description is used solely for optional keyword
relevance, never for the score.

The legacy bias-audit modules (`fairhire/stage*`, `fairhire/identity`) are
kept but are not part of this product path.
