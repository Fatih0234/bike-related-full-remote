Below is a “handoff-quality” explanation you can paste into your docs so any agent immediately understands **what the DB is**, **why it’s shaped this way**, and **how to work with it safely**.

---

# Database Architecture Overview

This database design supports a **live, recurring pipeline** that ingests citizen-reported Open311 events from Cologne and then runs **LLM-based labeling** in two phases. The main goals are:

1. **Idempotent ingestion** (safe to run every 3h/6h without duplicating data)
2. **Auditability** (we can prove what the API returned and what we did with it)
3. **Separation of concerns** (raw intake ≠ canonical truth ≠ model outputs)
4. **Cheap reprocessing** (improve rules/prompts later without re-fetching everything)
5. **Stable analytics/dashboarding** (Superset reads from stable structures)

At a high level we separate the system into three layers:

* **Ingestion layer:** `pipeline_runs`, `events_raw`, `events_rejected`, `events`
* **Labeling layer:** `event_phase1_labels`, `event_phase2_labels`
* **Analytics layer:** views like `v_bike_events` that pick the latest labels for dashboards

---

## Core idea: “Raw intake” vs “Canonical events” vs “Derived labels”

Open311 is **untrusted input**: users can submit spam, duplicates, empty reports, bad coordinates, etc.
We want to ingest regularly, but also keep the database clean for dashboards and LLM cost control.

So we store data in stages:

1. **`events_raw`** stores what we fetched (append-only)
2. **quality gate** decides accept/reject
3. accepted data becomes **`events`** (canonical)
4. LLM results go into **separate versioned tables** (`event_phase1_labels`, `event_phase2_labels`)
5. `v_bike_events` stitches everything together for analysis

This avoids the “giant single table with everything mixed” problem.

---

# Tables and their purposes

## 1) `pipeline_runs` — Run log + observability for cron jobs

**Purpose:** Every scheduled ingestion run (GitHub Actions cron) creates one run record.
This is your operational “black box flight recorder”.

**Why it exists:**

* Without it, a cron job fails and you don’t know *what happened* or *what changed*.
* You need counts and status to detect API shifts (“suddenly fetched_count dropped to 0”).

**Typical columns:**

* `run_id`: primary key referenced by other tables
* `started_at`, `finished_at`, `status`: success/failure tracking
* `fetch_window_start/end`: which time range was requested
* `fetched_count`, `inserted_count`, `rejected_count`: metrics
* `error_json`: store exception details safely (no secrets)

**Important behavior:**

* Create this row at the start.
* Update counts during/after ingestion.
* Mark `status='failed'` with `error_json` if something goes wrong.

---

## 2) `events_raw` — Append-only intake of API payloads

**Purpose:** Store *exactly what the API returned* for each run.

**Why it exists:**

* Auditability: “Did the API really return this record?”
* Reprocessing: if you improve parsing or rules, you can re-run off `events_raw` without refetching.
* Debugging: when weird stuff happens, raw payloads tell the truth.

**Key properties:**

* **Append-only**: don’t edit old rows
* Linked to `pipeline_runs` via `run_id`
* Has a `payload jsonb` with the full original record
* Also stores extracted “known” fields for convenience (`service_request_id`, `requested_at`, `lat/lon`, etc.)

**How it’s used:**

* Ingestion step always writes to `events_raw` first.
* Then quality gate reads raw rows and decides:

  * reject → write to `events_rejected`
  * accept → upsert into `events`

---

## 3) `events_rejected` — Quarantine bin with reasons

**Purpose:** Track events that were fetched but **not promoted** into canonical `events`.

**Why it exists:**

* Prevent silent data loss. If you simply “skip” you’ll never know what you skipped.
* Helps tune rules: you can inspect rejected items and refine your filters.
* Provides accountability: “we rejected X because of Y.”

**Key properties:**

* Each row points to a specific `events_raw.raw_id`
* Stores:

  * `reject_reason` (short string like `missing_coords`, `invalid_coords`, `duplicate_content`, `bad_payload`)
  * `reject_details` (JSON explaining the trigger; hashes, regex matches, etc.)

**Important behavior:**

* Rejected items do **not** go into canonical `events` (that’s the whole point).
* But they are not lost; they’re auditable and can be reconsidered later.

---

## 4) `events` — Canonical “gold” events table (stable)

**Purpose:** The stable dataset of “accepted” events.
This is what analytics and downstream labeling should rely on.

**Why it exists:**

* Dashboards want stable, clean rows.
* LLM processing should operate on cleaned records (and skip bad ones).
* Idempotency: one row per `service_request_id` (upsert target).

**Key properties:**

* Primary key: `service_request_id`
* Contains:

  * the essential fields from the API (title, description, requested_at, status, lat/lon, address_string, service_name, media_path)
  * your derived taxonomy fields (category/subcategory/subcategory2)
  * derived parsing outputs (year, sequence_number)
  * quality flags (`has_description`, `has_media`, `skip_llm`, etc.)
  * ingestion bookkeeping (`first_seen_at`, `last_seen_at`, `last_run_id`)

**Why no LLM outputs here?**
Because LLM outputs are:

* model/prompt/version dependent
* re-runnable
* not “truth” — they are derived interpretations

So they belong in separate label tables.

**Important behavior:**

* Ingestion uses **UPSERT**:

  * If `service_request_id` already exists, update status/media/etc and `last_seen_at`.
  * This supports repeated cron runs safely.

**Quality flags:**

* `has_description`: true if description has real text
* `skip_llm`: true if we should not send to LLM (e.g., no description)
* `is_link_only`, `is_flagged_abuse`: optional flags to control processing and dashboards

These flags are crucial for cost control and for avoiding garbage-in to prompts.

---

# Label tables (LLM outputs)

## 5) `event_phase1_labels` — Bike-related classification outputs (versioned)

**Purpose:** Store the results of Phase 1 LLM classification (bike related or not).

**Why versioned labels:**

* Prompts improve.
* Models change.
* You may want to re-label old events.
* You need to compare versions for evaluation.

So instead of overwriting columns, we append label rows.

**Key properties:**

* References `events(service_request_id)`
* Stores:

  * `model`, `prompt_version`
  * `input_hash` (hash of LLM input; prevents duplicate labeling)
  * outputs: `bike_related`, `confidence`, `evidence`, `reasoning`
* Unique constraint: `(service_request_id, prompt_version, input_hash)`

**How to use:**

* “Latest label wins” for dashboards.
* For experiments, you can compare across versions.

---

## 6) `event_phase2_labels` — Bike issue category outputs (versioned)

**Purpose:** Store Phase 2 LLM categorization for events that are bike-related.

Same logic as Phase 1:

* model/prompt versions
* `input_hash`
* outputs: `bike_issue_category`, `confidence`, evidence/reasoning
* unique constraint ensures idempotency per version+input

---

# Views for analytics

## 7) `v_bike_events` — Convenience view for dashboards

**Purpose:** Provide a single “dashboard-friendly” table by joining:

* canonical `events` +
* latest Phase 1 label +
* latest Phase 2 label

This keeps Superset simple:

* it reads one view
* you can change internal table structure without changing dashboards too much

**Important behavior:**

* The view should select the **latest label per event** (e.g., `distinct on (service_request_id) order by created_at desc`).
* Phase 2 fields will be NULL unless a Phase 2 label exists.

---

# Why this design fits your scenario

## A) Cron + incremental ingestion needs idempotency

If you pull every 3–6 hours, you will overlap windows and re-see items.
`events_raw` logs all fetches; `events` is protected by `service_request_id` upsert.

## B) Open311 input is noisy; we need a “gate”

We want to:

* keep empty descriptions (photo-only) but **skip LLM**
* reject obvious spam / broken records
  This is exactly what `events_rejected` + flags in `events` enable.

## C) LLM outputs change over time

Storing LLM outputs in the main `events` table makes re-runs and comparisons painful.
Versioned label tables make experimentation and improvements cheap and safe.

## D) Dashboards need stability

Superset wants a stable schema and “latest state”.
`v_bike_events` provides that, while internal changes can happen behind it.

---

# Most important “rules” for any agent working with this DB

1. **Never write LLM results into `events`.**
   Always write to `event_phase1_labels` / `event_phase2_labels`.

2. **Always ingest through the raw → gate → canonical flow.**

   * write API responses to `events_raw`
   * reject to `events_rejected`
   * accept/upsert to `events`

3. **Use `skip_llm` and `has_description` to control LLM cost.**
   If `has_description=false`, do not label.

4. **Treat labels as append-only and versioned.**
   New prompt? New `prompt_version`. Don’t overwrite old labels.

5. **Dashboards should read from the view, not label tables directly.**
   Keep `v_bike_events` as the stable interface.

