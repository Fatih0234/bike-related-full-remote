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
- first_accepted_service_request_id
- last_accepted_service_request_id
- min_accepted_requested_at
- max_accepted_requested_at
- duration_seconds (compute from started_at/finished_at)
