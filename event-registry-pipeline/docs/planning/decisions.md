# Decisions (ADR-lite)

## 001 - Separate raw, rejected, canonical tables

- **Decision:** Use `events_raw`, `events_rejected`, and `events` instead of a
  single wide table.
- **Why:** Auditability, safe reprocessing, and cleaner analytics.

## 002 - Versioned label tables

- **Decision:** Store Phase 1/Phase 2 outputs in append-only label tables.
- **Why:** Prompts and models evolve; versioned labels allow comparison and
  backfills without losing history.

## 003 - Incremental pulls by service_request_id

- **Decision:** Use the `sequence-year` format to fetch missing IDs directly.
- **Why:** Date-only queries miss newer entries; ID-based fetching is reliable.

## 004 - Use uv for environments

- **Decision:** Standardize on uv for sync and run.
- **Why:** Fast dependency resolution, consistent across agents.
