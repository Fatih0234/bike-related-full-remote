# Running locally

## Setup

```bash
cd /Volumes/T7/event-registry-pipeline
uv sync
cp .env.example .env
```

## Validate environment

```bash
uv run erp --help
uv run erp db check
```

## Dry-run ingestion

```bash
uv run erp ingest run --since 2026-01-01 --until 2026-01-07 --dry-run
```

Dry-run mode:
- fetches and evaluates
- prints counts and sample rows
- does **not** write to the database

Ensure `data/sags_uns_categories_3level.csv` is present for category enrichment.

## Incremental logic reminder

Date windows alone are not reliable for new events. The ingestion runner should
determine missing IDs using `service_request_id` sequencing and fetch them
directly via `/requests/{id}.json`.
