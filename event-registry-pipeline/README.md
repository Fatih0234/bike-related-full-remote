# Event Registry Pipeline

Unified ingestion and labeling pipeline for Cologne Open311 (Sag's uns) events.
This repo is the unified, production-oriented version of the work: it turns the
prototype into a repeatable pipeline you can run locally or on a schedule
(GitHub Actions cron), with auditability and idempotency.

## What this project does

### Implemented today
- **Ingestion (Phase 0):** fetches Cologne Open311 requests, stores every fetched
  payload in `public.events_raw` (append-only), applies a quality gate, writes
  rejects/warnings to `public.events_rejected`, and UPSERTs accepted records into
  `public.events`.
- **Incremental completeness:** compensates for the API’s unreliable date-window
  results via optional “gap fill” (ID sequencing) so you don’t silently miss new
  events.
- **Observability:** logs each run in `public.pipeline_runs` with metrics
  (fetched/staged/inserted/updated/rejected).
- **Dashboard contract:** `public.v_bike_events` exposes a stable schema for BI
  tools by joining canonical `events` with the latest labels (when labeling is
  enabled).

### Planned / scaffolding only (not implemented yet)
- **Phase 1 labeling** (`erp phase1 run`) and **Phase 2 labeling**
  (`erp phase2 run`) are currently stubs. They will later write to the
  versioned label tables:
  - `public.event_phase1_labels` (bike_related)
  - `public.event_phase2_labels` (bike_issue_category)

## Quickstart

```bash
cd /Volumes/T7/bike-related-full/event-registry-pipeline
uv sync
cp .env.example .env
uv run erp --help
uv run erp ingest run --since 2026-01-01 --until 2026-01-07 --dry-run
```

## Core model (tables you should know)

This pipeline uses a 3-layer model:

### Layer A — Ingestion (trusted vs untrusted)
- `public.pipeline_runs`: one row per run (status + metrics).
- `public.events_raw`: **append-only** raw intake (every fetched payload per run).
  Duplicates by `service_request_id` are expected across runs because this is an
  audit log.
- `public.events_rejected`: records items that were **not promoted** to canonical
  `events` *and* “accepted-but-needs-review” warnings (see `accepted` below).
- `public.events`: canonical, one row per `service_request_id` (UPSERT target).

### Layer B — Labeling (LLM, versioned)
- `public.event_phase1_labels`: append-only phase outputs (versioned).
- `public.event_phase2_labels`: append-only phase outputs (versioned).

### Layer C — Analytics
- `public.v_bike_events`: dashboard-friendly view built on canonical `events` +
  latest labels (the view schema is kept stable for Superset/BI).

## CLI commands (what you can run)

### Connectivity
- `uv run erp db check`: verifies DB connectivity.

### Ingestion (Phase 0)
- `uv run erp ingest run --since YYYY-MM-DD --until YYYY-MM-DD [--dry-run]`
  - Use for manual runs and backfills.
  - In `--dry-run`, no DB writes occur.
- `uv run erp ingest auto [--dry-run]`
  - Use for cron/scheduled runs.
  - Window policy:
    - `until = tomorrow (UTC date + 1 day)` to include “today”
    - `since = last successful pipeline_runs.fetch_window_end` (fallback: a small lookback)

### Labeling (Phase 1 / Phase 2)
- `uv run erp phase1 run --limit 200 [--dry-run]`
- `uv run erp phase2 run --limit 200 [--dry-run]`

Optional overrides:
- `--prompt-version p1_v006` / `--prompt-version p2_v001` (defaults from env)
- `--model-id gemini-2.5-flash-lite` (default from env)

## Ingestion: step-by-step (what happens on a live run)

Run: `erp ingest run --since ... --until ...` (without `--dry-run`)

1) Create a `pipeline_runs` row (`status='running'`).
2) Fetch `/requests.json` for the date window.
3) Optional gap-fill:
   - Determine the max `sequence-year` observed in the fetched window.
   - Compare with DB’s max stored `sequence_number` for that year.
   - Fetch any missing IDs via `/requests/{id}.json` (bounded by a limit).
4) Insert all fetched items into `events_raw` (append-only, for audit/debug).
5) Quality gate:
   - Reject broken/spam/strict-duplicate items → `events_rejected(accepted=false)`.
   - Accept valid items → UPSERT into `events`.
   - Accept but “needs review” (e.g. unmapped service_name) → write a warning row
     into `events_rejected(accepted=true)` while still inserting into `events`.
6) Update the `pipeline_runs` row with counts and mark `status='success'`.
7) On error: mark `status='failed'` and populate `error_json`.

## Quality gate rules (current behavior)

### True rejects (`events_rejected.accepted=false`)
- Missing/invalid `service_request_id`
- Missing/invalid `requested_datetime`
- Missing/invalid coordinates
- Missing `service_name`, `title`, or `address_string`
- Invalid `status` (must be `open` or `closed`)
- Spam description (very small set of exact terms; see code)
- Strict duplicates (normalized description + rounded coords + time window)

### Accepted but skip LLM (`events.skip_llm=true`)
- Empty/whitespace description
- Link-only description (mostly URLs)

### Warnings (`events_rejected.accepted=true`)
- Unmapped `service_name` (accepted into `events` but logged for review)

## “Gap fill” (why it exists)

Cologne Open311 date window queries can miss records. To avoid silent gaps, the
pipeline uses the fact that `service_request_id` encodes sequence and year
(e.g. `2089-2026`).

Gap fill computes missing IDs between:
- DB max `sequence_number` (what you already have), and
- the max sequence observed in the API window

…and fetches those IDs directly via `/requests/{id}.json`.

## Running on GitHub Actions (cron)

This repo includes a cron workflow: `.github/workflows/ingest-cron.yml`

### Required GitHub secrets
- `DATABASE_URL` (Supabase Postgres connection string)

### How to test
1) Push to GitHub
2) In GitHub UI: Actions → `ingest-cron` → “Run workflow”
3) Verify a new row appears in `public.pipeline_runs` with `status='success'`

Concurrency is enabled to prevent overlapping scheduled runs.

## DB setup (bootstrap and migrations)

For a fresh database, apply `scripts/bootstrap_db.sql`.

If your DB already exists, apply migrations under `scripts/migrations/` as
needed. See `docs/database/migrations.md`.

## Common inspection queries

### Latest runs
```sql
select run_id, started_at, finished_at, status,
       fetched_count, staged_count, inserted_count, updated_count, rejected_count
from public.pipeline_runs
order by run_id desc
limit 10;
```

### Raw rows for a specific run (avoid “duplicates” confusion)
```sql
select *
from public.events_raw
where run_id = 123
order by raw_id desc
limit 200;
```

### True rejects vs warnings
```sql
select accepted, reject_reason, count(*)
from public.events_rejected
group by accepted, reject_reason
order by accepted, count(*) desc;
```

## Project layout

- `src/erp/` - pipeline code (ingestion, labeling, CLI)
- `docs/` - architecture, operations, planning, legacy notes
- `data/` - static resources like category mappings
- `prompts/` - versioned LLM prompts (phase1/phase2)
- `scripts/` - database bootstrap and helper scripts

## Documentation

- `docs/overview.md`
- `docs/architecture.md`
- `docs/database/schema.md`
- `docs/database/database-doc.md`
- `docs/operations/running-locally.md`
- `docs/operations/ingestion.md`
- `docs/operations/incremental-ingestion.md`
- `docs/planning/agent-brief.md`

## Notes

- Incremental ingestion is based on `service_request_id` sequencing, not just
  timestamps, to avoid missed API entries.
- Category enrichment uses `data/sags_uns_categories_3level.csv`.
