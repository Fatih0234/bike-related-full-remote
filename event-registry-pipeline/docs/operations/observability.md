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
- staged_count
- rejected_count
- inserted_count
- updated_count
- duration_seconds
- duration_seconds
