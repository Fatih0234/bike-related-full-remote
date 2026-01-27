# Ingestion flow

This document describes the Phase 0 ingestion pipeline from Open311 into
Supabase Postgres.

## High-level flow

1. Create a `pipeline_runs` row (status=running, `run_id` is bigserial).
2. Fetch Open311 requests for the provided date window.
3. Optionally gap-fill missing IDs based on `service_request_id` sequencing.
4. Write all fetched payloads to `events_raw` (append-only).
5. Apply the quality gate:
   - reject broken/spam/duplicate submissions into `events_rejected`
   - accept valid records and UPSERT into `events`
   - log “accepted with warning” cases (e.g., unmapped service_name) into
     `events_rejected` with `reject_details.accepted=true`
6. Update `pipeline_runs` with counts (`fetched_count`, `staged_count`,
   `inserted_count`, `updated_count`, `rejected_count`) and mark status=success.
7. On failure, mark status=failed with `error_json`.

## Key invariants

- `events_raw` is append-only.
- `events` has one row per `service_request_id` (UPSERT).
- Every rejected record must be logged in `events_rejected`.

## Incremental gap fill

Because the API can miss entries in date windows, we compute gaps by sequence:

1. Determine the maximum sequence observed in the window for each year.
2. Query `events` for the latest stored sequence per year.
3. Fetch missing IDs via `/requests/{id}.json`.
4. Track 404s as `missing_id_404_count`.

This is controlled by `INGESTION_ENABLE_GAP_FILL` and `INGESTION_GAP_FILL_LIMIT`,
or via CLI flags `--no-gap-fill` and `--gap-fill-limit`.

## Quality gate (V1)

Rejects:
- missing or invalid `service_request_id`
- missing or invalid `requested_at`
- missing/invalid coordinates
- unmapped `service_name` is accepted but logged for review
- strict duplicates (normalized description + rounded coords + time window)
- spam text (e.g., "test", "asdf")

Strict duplicate behavior is controlled by:
- `DUPLICATE_WINDOW_HOURS`
- `DUPLICATE_COORD_PRECISION`

Accept but skip LLM:
- empty description
- link-only description (URLs only)

## Dry-run

`--dry-run` evaluates fetch + quality gate without writing to the database.
It prints counts and top reject reasons for inspection.

## Cron / auto window

For scheduled ingestion, prefer `erp ingest auto` which derives a safe window
from the database and uses an “until = tomorrow” policy to include today.

## Environment variables

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes* | - | PostgreSQL connection string |
| `PGHOST` | Yes* | - | PostgreSQL host (alternative to DATABASE_URL) |
| `PGPORT` | No | 5432 | PostgreSQL port |
| `PGUSER` | Yes* | - | PostgreSQL username |
| `PGPASSWORD` | Yes* | - | PostgreSQL password |
| `PGDATABASE` | Yes* | - | PostgreSQL database name |

*Either `DATABASE_URL` or all `PG*` variables must be set.

### Open311 API

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPEN311_BASE_URL` | No | `https://sags-uns.stadt-koeln.de/georeport/v2` | Open311 API base URL |
| `OPEN311_TIMEOUT_SECONDS` | No | 30 | HTTP request timeout |
| `OPEN311_PAGE_SIZE` | No | 100 | Items per page for pagination |
| `OPEN311_USE_EXTENSIONS` | No | true | Include extended metadata |
| `OPEN311_MAX_WORKERS` | No | 10 | Parallel workers for gap-fill |
| `OPEN311_MAX_RETRIES` | No | 3 | Retry attempts for 5xx errors |

### Ingestion behavior

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `INGESTION_OVERLAP_HOURS` | No | 12 | Hours to extend fetch window backwards |
| `INGESTION_ENABLE_GAP_FILL` | No | true | Enable ID-based gap filling |
| `INGESTION_GAP_FILL_LIMIT` | No | 5000 | Max gap-fill fetches per run |
| `DUPLICATE_WINDOW_HOURS` | No | 24 | Time window for duplicate detection |
| `DUPLICATE_COORD_PRECISION` | No | 4 | Decimal places for coordinate rounding |
| `DUPLICATE_REQUIRE_SERVICE_NAME` | No | true | Require service_name match for duplicates |
| `DUPLICATE_REQUIRE_ADDRESS` | No | false | Require address match for duplicates |
| `LINK_ONLY_MIN_CHARS` | No | 3 | Min non-URL chars to not be link-only |

### Runtime

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `RUN_ENV` | No | local | Environment identifier |

## Troubleshooting

### Common errors

**"DATABASE_URL or PG* env vars must be set"**
- Ensure `.env` file exists with database credentials
- Check that the file is in the project root

**"Category mapping not found"**
- Ensure `data/sags_uns_categories_3level.csv` exists
- Run from the project root directory

**Connection refused / timeout**
- Verify database is running and accessible
- Check firewall rules for Supabase connections
- Verify SSL mode if using cloud database

**"duplicate key value violates unique constraint"**
- This shouldn't happen with UPSERT; check for concurrent runs
- Verify `service_request_id` uniqueness in source data

### Recovery from failed runs

1. Check `pipeline_runs` for the failed run:
   ```sql
   SELECT * FROM pipeline_runs WHERE status = 'failed' ORDER BY started_at DESC;
   ```

2. Examine `error_json` for details

3. Fix the issue and re-run with the same date window:
   ```bash
   erp ingest run --since YYYY-MM-DD --until YYYY-MM-DD
   ```

4. The UPSERT logic ensures idempotency - re-running is safe
