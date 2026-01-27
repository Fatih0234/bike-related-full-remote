# Database schema

This schema is optimized for recurring ingestion, auditability, and versioned
LLM labels. It follows a raw -> gate -> canonical flow with append-only labels.

## Core tables

### pipeline_runs

Tracks each ingestion run for observability and debugging.

Suggested columns:
- `run_id` (bigserial, primary key)
- `started_at`, `finished_at`, `status`
- `fetch_window_start`, `fetch_window_end`
- `fetched_count`, `staged_count`, `rejected_count`
- `inserted_count`, `updated_count`
- `error_json` (jsonb)

### events_raw

Append-only storage of API payloads.

Suggested columns:
- `raw_id` (bigserial, primary key)
-- `run_id` (bigint, references pipeline_runs)
- `service_request_id`, `requested_at`, `service_name`
- `lat`, `lon`, `address_string`, `status`
- `media_path` (relative file path)
- `payload` (jsonb, full API response)
- `created_at`

### events_rejected

Quarantine for records that fail the quality gate.

Suggested columns:
- `raw_id` (primary key, references events_raw)
- `run_id`
- `service_request_id`
- `accepted` (boolean; true for accepted-but-review warnings)
- `reject_reason` (text)
- `reject_details` (jsonb)
- `created_at`

### events

Canonical, stable events table. One row per `service_request_id`.

Suggested columns:
- `service_request_id` (primary key)
- `title`, `description`, `description_redacted`, `requested_at`, `status`
- `lat`, `lon`, `address_string`
- `service_name`, `category`, `subcategory`, `subcategory2`
- `media_path`, `year`, `sequence_number`
- `media_path`, `year`, `sequence_number`
- `has_description`, `has_media`, `skip_llm`, `is_link_only`, `is_flagged_abuse`
- `first_seen_at`, `last_seen_at`, `last_run_id`

Recommended indexes:
- `requested_at`, `status`, `category`, `subcategory`
- `(year, sequence_number)` for incremental pull logic
- Geospatial index if PostGIS is enabled

## Label tables (versioned)

### event_phase1_labels

Stores bike-related classification outputs. Append-only.

Suggested columns:
- `label_id` (bigserial, primary key)
- `service_request_id` (references events)
- `prompt_version`, `model_id`, `input_hash`
- `label`, `confidence`, `evidence`, `reasoning`
- `created_at`

Unique constraint: `(service_request_id, prompt_version, input_hash)`.

### event_phase2_labels

Stores issue category outputs for bike-related events. Append-only.

Suggested columns:
- `label_id` (bigserial, primary key)
- `service_request_id` (references events)
- `prompt_version`, `model_id`, `input_hash`
- `category`, `confidence`, `evidence`, `reasoning`
- `created_at`

Unique constraint: `(service_request_id, prompt_version, input_hash)`.

## Analytics view

### v_bike_events

Dashboard-friendly view that joins `events` with the latest Phase 1 and Phase 2
labels (latest by `created_at`). Phase 2 columns are nullable.

## Why this design

- **Idempotency:** repeated runs are safe via UPSERT on `events`.
- **Auditability:** raw payloads are preserved in `events_raw`.
- **Reprocessing:** labels are versioned and append-only.
- **Cost control:** `skip_llm` keeps empty descriptions out of labeling.

For the full philosophy and design rationale, see `docs/database/database-doc.md`.
