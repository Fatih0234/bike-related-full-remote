# Observability

## Run logging

- Each ingestion run creates a `pipeline_runs` row.
- Update counts as data flows through raw -> rejected -> canonical.
- Persist errors to `error_json` so failures are visible in SQL.

## Application logs

- Use structured, consistent logging in `erp.utils.logging`.
- Prefer INFO for run progress, WARNING for recoverable issues, ERROR for
  failures.

## Recommended metrics

- fetched_count
- raw_inserted_count
- rejected_count
- canonical_upserted_count
- missing_id_404_count
- duration_seconds
