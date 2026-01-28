# Labeling (Phase 1 + Phase 2)

This pipeline has two LLM labeling phases:

- **Phase 1:** bike relevance (TRUE / FALSE / UNCERTAIN)
- **Phase 2:** issue categorization (9 fixed categories)

Both phases are **append-only** and **versioned**.

## Required env vars

- `DATABASE_URL` (Postgres connection string)
- `GOOGLE_API_KEY` (Gemini)

Optional:

- `GEMINI_MODEL_ID` (default: `gemini-2.5-flash-lite`)
- `PHASE1_PROMPT_VERSION` (default: `p1_v006`)
- `PHASE2_PROMPT_VERSION` (default: `p2_v001`)

## Phase 1: what gets labeled

Phase 1 selects from `public.events` where:

- `skip_llm = false`
- `has_description = true`
- no existing row in `public.event_phase1_labels` for the same:
  - `service_request_id`
  - `prompt_version`
  - `input_hash`

### UNCERTAIN handling

Phase 1 output label `"uncertain"` is stored as:

- `event_phase1_labels.bike_related = NULL`

This preserves uncertainty without forcing it into `true/false`.

## Phase 2: what gets labeled

Phase 2 labels only events where the **latest** Phase 1 label has:

- `bike_related = true`

It also skips anything already labeled for the same `(service_request_id, prompt_version, input_hash)`.

## CLI usage

From `event-registry-pipeline/`:

- Dry-run (no DB writes): `uv run erp phase1 run --limit 5 --dry-run`
- Live write: `uv run erp phase1 run --limit 200`
- Phase 2: `uv run erp phase2 run --limit 200`

You can override defaults:

- `--prompt-version p1_v006` / `--prompt-version p2_v001`
- `--model-id gemini-2.5-flash-lite`

## What gets written

- Phase 1 → `public.event_phase1_labels`
- Phase 2 → `public.event_phase2_labels`

## Run tracking

Every Phase 1/Phase 2 execution writes a row to:

- `public.labeling_runs`

This is the labeling equivalent of `public.pipeline_runs` for ingestion.

The dashboard should continue reading from:

- `public.v_bike_events` (joins canonical events with latest labels)
