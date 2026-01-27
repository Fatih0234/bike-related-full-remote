# Running locally

## Setup

```bash
cd /Volumes/T7/bike-related-full/event-registry-pipeline
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

## Scheduled-style local run (auto window)

```bash
uv run erp ingest auto --dry-run
uv run erp ingest auto
```

Optional gap-fill controls:

```bash
uv run erp ingest run --since 2026-01-01 --until 2026-01-07 --gap-fill-limit 200
uv run erp ingest run --since 2026-01-01 --until 2026-01-07 --no-gap-fill
```

Dry-run mode:
- fetches and evaluates
- prints counts and sample rows
- does **not** write to the database

Ensure `data/sags_uns_categories_3level.csv` is present for category enrichment.
If your database predates new columns, apply the migration scripts in
`scripts/migrations/` before running a real write.

For full ingestion details, see `docs/operations/ingestion.md`.

## Live API tests (optional)

```bash
uv sync --extra dev
RUN_LIVE_API_TESTS=1 uv run pytest tests/test_open311_live.py
```

## Incremental logic reminder

Date windows alone are not reliable for new events. The ingestion runner should
determine missing IDs using `service_request_id` sequencing and fetch them
directly via `/requests/{id}.json`.
