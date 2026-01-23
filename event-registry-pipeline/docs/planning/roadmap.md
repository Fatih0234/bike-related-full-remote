# Roadmap

## Phase 0: Ingestion skeleton

- Build ingestion CLI with raw -> gate -> canonical flow.
- Implement `service_request_id` gap fill fetcher.
- Wire up run logging in `pipeline_runs`.

## Phase 1: Bike-related labeling

- Implement prompt loading and Phase 1 runner.
- Store versioned labels and input hashes.
- Add skip-LLM rules for empty descriptions and excluded categories.

## Phase 2: Issue categorization

- Implement Phase 2 runner and category schema.
- Add eval runs and basic metrics output.

## Observability + dashboards

- Create `v_bike_events` view and dashboard-friendly fields.
- Build simple monitoring queries for run health.

## Backfills + re-labeling

- Historical backfills by year using ID-range fetch.
- Re-label events with new prompt versions.

## Quality gate improvements

- Duplicate detection across time window.
- Coordinate validation and outlier filtering.
