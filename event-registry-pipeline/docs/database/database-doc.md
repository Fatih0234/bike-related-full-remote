# Database architecture overview

This database design supports a live, recurring pipeline that ingests citizen-
reported Open311 events from Cologne and then runs LLM-based labeling in two
phases. The main goals are:

1. Idempotent ingestion (safe to run every 3h/6h without duplicating data)
2. Auditability (we can prove what the API returned and what we did with it)
3. Separation of concerns (raw intake != canonical truth != model outputs)
4. Cheap reprocessing (improve rules/prompts later without re-fetching)
5. Stable analytics/dashboarding (Superset reads from stable structures)

At a high level we separate the system into three layers:

- Ingestion layer: pipeline_runs, events_raw, events_rejected, events
- Labeling layer: event_phase1_labels, event_phase2_labels
- Analytics layer: views like v_bike_events that pick the latest labels

## Core idea: raw intake vs canonical events vs derived labels

Open311 is untrusted input: users can submit spam, duplicates, empty reports,
bad coordinates, etc. We want to ingest regularly, but also keep the database
clean for dashboards and LLM cost control.

So we store data in stages:

1. events_raw stores what we fetched (append-only)
2. quality gate decides accept/reject
3. accepted data becomes events (canonical)
4. LLM results go into separate versioned tables
5. v_bike_events stitches everything together for analysis

This avoids the giant single table with everything mixed problem.

## Tables and their purposes

### 1) pipeline_runs - run log and observability for cron jobs

Purpose: every scheduled ingestion run creates one run record. This is your
operational flight recorder.

Why it exists:

- Without it, a cron job fails and you do not know what happened or what changed.
- You need counts and status to detect API shifts (suddenly fetched_count is 0).

Typical columns:

- run_id: primary key referenced by other tables
- started_at, finished_at, status: success/failure tracking
- fetch_window_start/end: which time range was requested
- fetched_count, inserted_count, rejected_count: metrics
- error_json: store exception details safely (no secrets)

Important behavior:

- Create this row at the start.
- Update counts during/after ingestion.
- Mark status=failed with error_json if something goes wrong.

### 2) events_raw - append-only intake of API payloads

Purpose: store exactly what the API returned for each run.

Why it exists:

- Auditability: did the API really return this record?
- Reprocessing: if you improve parsing or rules, you can re-run off events_raw
  without refetching.
- Debugging: when weird stuff happens, raw payloads tell the truth.

Key properties:

- Append-only: do not edit old rows
- Linked to pipeline_runs via run_id
- Has a payload jsonb with the full original record
- Stores extracted fields for convenience (service_request_id, requested_at,
  lat/lon, etc.)

How it is used:

- Ingestion step always writes to events_raw first.
- Then quality gate reads raw rows and decides:
  - reject -> write to events_rejected
  - accept -> upsert into events

### 3) events_rejected - quarantine bin with reasons

Purpose: track events that were fetched but not promoted into canonical events.

Why it exists:

- Prevent silent data loss. If you skip, you will never know what you skipped.
- Helps tune rules: inspect rejected items and refine filters.
- Provides accountability: we rejected X because of Y.

Key properties:

- Each row points to a specific events_raw.raw_id
- Stores reject_reason and reject_details for later analysis

Important behavior:

- Rejected items do not go into canonical events.
- They are not lost and can be reconsidered later.

### 4) events - canonical gold events table

Purpose: stable dataset of accepted events for analytics and labeling.

Why it exists:

- Dashboards want stable, clean rows.
- LLM processing should operate on cleaned records.
- Idempotency: one row per service_request_id (upsert target).

Key properties:

- Primary key: service_request_id
- Contains essential fields from the API (title, description, requested_at,
  status, lat/lon, address_string, service_name, media_path)
- Derived taxonomy fields (category/subcategory/subcategory2)
- Derived parsing outputs (year, sequence_number)
- Quality flags (has_description, skip_llm, etc.)
- Ingestion bookkeeping (first_seen_at, last_seen_at, last_run_id)

Why no LLM outputs here?

- LLM outputs are model/prompt/version dependent
- They are re-runnable
- They are not truth - they are derived interpretations

So they belong in separate label tables.

Important behavior:

- Ingestion uses UPSERT
- If service_request_id already exists, update status/media/etc and last_seen_at
- This supports repeated cron runs safely

Quality flags:

- has_description: true if description has real text
- has_media: true if media_path exists
- skip_llm: true if we should not send to LLM (e.g., no description)
- is_link_only, is_flagged_abuse: optional flags to control processing

These flags are crucial for cost control and avoiding garbage-in to prompts.

## Label tables (LLM outputs)

### 5) event_phase1_labels - bike-related classification (versioned)

Purpose: store the results of Phase 1 LLM classification (bike related or not).

Why versioned labels:

- Prompts improve
- Models change
- You may want to re-label old events
- You need to compare versions for evaluation

So instead of overwriting columns, we append label rows.

Key properties:

- References events(service_request_id)
- Stores model, prompt_version, input_hash
- Outputs: bike_related, confidence, evidence, reasoning
- Unique constraint: (service_request_id, prompt_version, input_hash)

How to use:

- Latest label wins for dashboards
- Compare across versions for experiments

### 6) event_phase2_labels - bike issue categories (versioned)

Purpose: store Phase 2 LLM categorization for events that are bike-related.

Same logic as Phase 1:

- model/prompt versions
- input_hash
- outputs: bike_issue_category, confidence, evidence/reasoning
- unique constraint ensures idempotency per version+input

## Views for analytics

### 7) v_bike_events - convenience view for dashboards

Purpose: provide a single dashboard-friendly table by joining:

- canonical events
- latest Phase 1 label
- latest Phase 2 label

This keeps Superset simple:

- it reads one view
- internal table changes do not break dashboards

Important behavior:

- The view selects the latest label per event
- Phase 2 fields are NULL unless a Phase 2 label exists

## Why this design fits the scenario

### A) Cron and incremental ingestion needs idempotency

If you pull every 3-6 hours, you will overlap windows and re-see items.
events_raw logs all fetches; events is protected by service_request_id upsert.

### B) Open311 input is noisy; we need a gate

We want to:

- keep empty descriptions (photo-only) but skip LLM
- reject obvious spam or broken records

This is exactly what events_rejected and quality flags enable.

### C) LLM outputs change over time

Storing LLM outputs in events makes re-runs and comparisons painful.
Versioned label tables make experimentation and improvements cheap and safe.

### D) Dashboards need stability

Superset wants a stable schema and latest state. v_bike_events provides that
while internal changes can happen behind it.

## Most important rules for any agent

1. Never write LLM results into events.
2. Always ingest through the raw -> gate -> canonical flow.
3. Use skip_llm and has_description to control LLM cost.
4. Treat labels as append-only and versioned.
5. Dashboards should read from the view, not label tables directly.
