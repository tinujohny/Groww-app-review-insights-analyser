# App Review Insights Analyser

Phase 1 delivers typed configuration, review schemas, and service contracts for the weekly review pulse pipeline described in `ARCHITECTURE.md`. **Each phase has its own Python package and data folder** — code under `src/phase1/` … `src/phase4/`; optional artifacts under `data/phase1/` … `data/phase4/`. The umbrella package `review_pulse` re-exports Phase 1 types for convenience.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Refresh on-disk Phase 1 data (redacted settings + schema snapshot):

```bash
review-pulse-phase1
```

Writes `data/phase1/phase1_manifest.json` (override path with `-o` / `--output`).

Ingest a public review export (Phase 2):

```bash
review-pulse-phase2-ingest path/to/reviews.csv --source google_play
# or --source app_store
# Add --no-phase3 to skip language/emoji filters; --json-out / --stats-out (e.g. under data/phase2/)
```

**Collect reviews over the network** (saved under `data/phase2/` by default):

```bash
# Apple: public iTunes customer-reviews RSS (no login). Find app id in the App Store URL (?id=…)
review-pulse-collect app_store --app-id YOUR_APP_ID --country us --target 500

# Google Play: unofficial public-page scraper (set package / application id)
review-pulse-collect google_play --package com.example.app --target 500
```

`--target` defaults to **`REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT`** (often **500**) and never exceeds it. The pipeline still enforces **minimum word count**, **allowed languages** (`REVIEW_PULSE_REVIEW_LANGUAGES`), and **emoji removal** (`REVIEW_PULSE_DROP_REVIEWS_WITH_EMOJIS`) unless you pass `--no-phase3`.

Optional env defaults: `REVIEW_PULSE_APP_STORE_APP_ID`, `REVIEW_PULSE_GOOGLE_PLAY_PACKAGE`. Use `--no-phase3` only if you want normalized rows without language/emoji filtering.

Configure limits and secrets via environment variables (see `.env.example`). `REVIEW_PULSE_MAX_REVIEWS_PER_EXPORT` defaults to **500** to match common single-export caps; set it higher when your download source allows (e.g. 5000). Review **titles are not stored**; only body `text` is used. `REVIEW_PULSE_MIN_REVIEW_WORDS` defaults to **5** — shorter reviews are dropped. `REVIEW_PULSE_REVIEW_LANGUAGES` defaults to **`en`** — non-matching languages are removed using `langdetect` (see `phase3.language_filter`). **`REVIEW_PULSE_DROP_REVIEWS_WITH_EMOJIS`** defaults to **true** — reviews with emoji in the body are removed (`phase3.emoji_filter`).

## Phase 4 — themes (Groq)

Use the **filtered** Phase 2 JSONL (same file `review-pulse-collect` / `review-pulse-phase2-ingest` writes after Phase 3 rules). Set `REVIEW_PULSE_GROQ_API_KEY` in `.env` (optional `REVIEW_PULSE_GROQ_MODEL`).

```bash
review-pulse-phase4-themes --input data/phase2/collected_500_reviews.jsonl
# optional: --out data/phase4/my_themes.json  --max-chars 80000  --max-reviews 500
```

**Multiple requests:** use `--chunked` to split the corpus into several Groq calls (each up to `--max-chars`). By default, a **merge** step runs afterward so you still get one consolidated `themes` list (`merge_raw_response` / `merge_parsed`). Use `--no-merge` to keep only per-batch results under `batches`.

```bash
review-pulse-phase4-themes -i data/phase2/collected_500_reviews.jsonl --chunked --max-chars 20000
```

Writes `data/phase4/themes_<UTC-timestamp>.json` with canonical `themes` and `review_theme_map` (plus raw responses / provider metadata).

## Phase 5 — weekly pulse note

Generate the weekly note (top 3 themes, 3 quotes, 3 action ideas) from the Phase 4 artifact and Phase 2 sanitized corpus:

```bash
review-pulse-phase5-note --phase4 data/phase4/themes_latest.json --phase2 data/phase2/collected_500_reviews.jsonl
# optional: --out data/phase5/weekly_pulse.json
```

Writes `data/phase5/weekly_pulse_<UTC-timestamp>.json` with:
- `topThemes` (with evidence volume),
- `quotes` (verbatim, mapped to `review_id_internal`),
- `actionIdeas` (`effort`/`impact` tags),
- `noteText` and `wordCount` (guardrail <=250),
- `policy` quality checks (`unique_quotes_ok`, `quote_source_map_ok`, etc.).

## Phase 6 — email draft

Create a draft artifact from the Phase 5 weekly pulse:

```bash
review-pulse-phase6-draft --phase5 data/phase5/weekly_pulse.json
# optional: --out data/phase6/email_draft.json
# frontend/runtime recipient override:
#   --to-email recipient@company.com
#   --recipient-name "Priya"
```

Subject format is `Groww Weekly Review Pulse - YYYY-WW`. The body includes the weekly note plus a metadata footer (`week_range`, `review_count`, timestamp). On provider failure, the draft payload is still persisted and a retry job is appended to `data/phase6/retry_queue.jsonl`.
If `recipientName` is provided (`--recipient-name` or `phase5.recipientName`), the mail starts with a personalized greeting: `Hi <name>,`.

## Phase 7 — CLI + Web UI integration (FastAPI + Next.js)

Phase 7 exposes a small local HTTP API that the Web UI can call to run the weekly pipeline (Phase 4 -> Phase 5 -> Phase 6) for a given week bucket.

### Stakeholder alignment (exports, window, artifacts)

- **CSV-only / no auto-scrape:** set `REVIEW_PULSE_DISABLE_REMOTE_COLLECT=true` so the Phase 7 API does not fall back to App Store RSS or Play scraping when no Phase 2 JSONL exists. Ingest storefront CSVs with `review-pulse-phase2-ingest` instead.
- **Rolling window:** `review-pulse-scheduler` defaults to `--weeks-back 12` (use `--weeks-back 8` for a shorter lookback).
- **Theme legend:** Phase 4 output lists `themes` (name and supporting text). Use that JSON or the Web UI “Download Markdown” export for a readable theme summary alongside the weekly note.
- **Internal IDs:** `review_id_internal` may appear in internal JSON for traceability; stakeholder-facing copy (email body, note) uses verbatim quotes only.

### Run backend

```bash
review-pulse-api
```

Default: `http://127.0.0.1:8000`.

### Run Web UI (Next.js)

```bash
cd webui
npm install
npm run dev
```

Configure `NEXT_PUBLIC_API_BASE_URL` (default is `http://127.0.0.1:8000`).
For provider auth, set `REVIEW_PULSE_EMAIL_USERNAME` and `REVIEW_PULSE_EMAIL_PASSWORD` in `.env` (plus `REVIEW_PULSE_EMAIL_PROVIDER`).

## Deploy: Backend on Railway, Frontend on Vercel

### Railway (backend / FastAPI via Docker)

This repo supports Railway Docker deploy using:

- `Dockerfile`
- `railway.toml` (`builder = "DOCKERFILE"`)

Railway will build and run `review-pulse-api` from the container. The API reads `PORT` automatically.
The container does not rely on committed `data/` artifacts unless you ship them; otherwise API fallback collection runs when no local Phase 2 JSONL is present and `REVIEW_PULSE_DISABLE_REMOTE_COLLECT` is not set.

Set these Railway environment variables:

- `REVIEW_PULSE_GROQ_API_KEY`
- `REVIEW_PULSE_GEMINI_API_KEY`
- `REVIEW_PULSE_GEMINI_MODEL=gemini-2.5-flash`
- `REVIEW_PULSE_EMAIL_PROVIDER=gmail`
- `REVIEW_PULSE_EMAIL_USERNAME`
- `REVIEW_PULSE_EMAIL_PASSWORD`
- `REVIEW_PULSE_CORS_ORIGINS=https://<your-vercel-app>.vercel.app`

Notes:

- Server binds to `0.0.0.0` and uses `PORT` automatically (Railway compatible).
- `REVIEW_PULSE_CORS_ORIGINS` accepts either `*` or a comma-separated list of origins.
- Keep secrets only in Railway Variables (do not commit `.env`).

### Vercel (frontend / Next.js)

Deploy from `webui/` as the project root (or set Vercel "Root Directory" = `webui`).

Set frontend env var in Vercel:

- `NEXT_PUBLIC_API_BASE_URL=https://web-production-628ea.up.railway.app`

Then redeploy the frontend so browser calls go to Railway backend.
