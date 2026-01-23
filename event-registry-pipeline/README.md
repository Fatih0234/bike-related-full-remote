# Event Registry Pipeline

Unified ingestion and labeling pipeline for Cologne Open311 (Sag's uns) events.
This repo scaffolds the full flow from API intake to LLM labeling and dashboards,
with a clean architecture and strong documentation for future agents.

## What this project does

- Ingests Open311 requests into `events_raw`, applies a quality gate, and upserts
  canonical rows into `events`.
- Runs Phase 1 (bike-related classification) and Phase 2 (bike issue category)
  using versioned prompts and append-only label tables.
- Supports idempotent cron runs and future dashboards via stable views.

## Quickstart

```bash
cd /Volumes/T7/event-registry-pipeline
uv sync
cp .env.example .env
uv run erp --help
uv run erp ingest run --since 2026-01-01 --until 2026-01-07 --dry-run
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
- `docs/operations/incremental-ingestion.md`
- `docs/planning/agent-brief.md`

## Notes

- Incremental ingestion is based on `service_request_id` sequencing, not just
  timestamps, to avoid missed API entries.
- Category enrichment uses `data/sags_uns_categories_3level.csv`.
