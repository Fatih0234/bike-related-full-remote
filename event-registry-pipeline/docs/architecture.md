# Architecture

## Module boundaries

- `erp.ingestion` handles API fetching, quality gating, and writes.
- `erp.db` contains database connectivity helpers.
- `erp.labeling` runs Phase 1/Phase 2 LLM workflows.
- `erp.cli` wires commands for local runs and cron jobs.
- `erp.utils` provides logging, hashing, and normalization helpers.

## Raw vs canonical vs labels

- **Raw intake** (`events_raw`) is append-only and stores the full payload.
- **Canonical events** (`events`) are stable, deduplicated rows keyed by
  `service_request_id`.
- **Labels** are stored separately in versioned tables and never overwrite
  canonical data.

## Idempotency strategy

- Every cron run creates a `pipeline_runs` record and attaches `run_id` to raw
  inserts.
- `events` uses UPSERT on `service_request_id` to update status/media and track
  `last_seen_at` without duplicating records.
- Label tables are append-only with unique constraints on
  `(service_request_id, prompt_version, input_hash)`.

## Incremental ingestion using service_request_id

Date-based API queries do not reliably return the latest requests. To avoid
missing entries, the incremental strategy is based on `service_request_id`:

- Format: `sequence-year` (example: `132-2025` = 132nd event in 2025).
- Fetch a recent date window to discover the **current maximum sequence** for
  the active year.
- Compare this to the **last stored sequence** in `events` for that year.
- Fetch missing IDs directly using `/requests/{service_request_id}.json` for the
  range `(last_sequence + 1) .. max_sequence`.
- Treat 404 as deleted/non-existent; record the miss in run metrics.

Example: if the latest stored event is `34-2026` and the API shows `100-2026` as
the newest sequence, request IDs `35-2026` through `100-2026` are fetched
directly. This ensures we fill gaps that the date-based endpoint skips.

## Data enrichment rules

- `service_name` maps to a 3-level category hierarchy using
  `data/sags_uns_categories_3level.csv`.
- `media_path` is stored as the relative `/files/...` segment to avoid bloating
  storage with long URLs.
- `year` and `sequence_number` are derived from `service_request_id`.

## Skip LLM when no description

If `description` is empty, the event is stored but `skip_llm=true` to avoid
unnecessary labeling calls.

## Extension points

- Implement a stricter quality gate for duplicates and spam.
- Add retries/backoff in API fetchers and LLM calls.
- Implement `v_bike_events` view for dashboards.
