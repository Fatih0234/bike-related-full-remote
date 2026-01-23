# Task backlog

## Ingestion

- [ ] Implement Open311 paging with retries and timeouts
- [ ] Implement ID-gap fetching based on `service_request_id`
- [ ] Write raw payloads to `events_raw`
- [ ] Implement quality gate and rejection reasons
- [ ] Upsert canonical events with `first_seen_at`/`last_seen_at`

Definition of done:
- Dry-run mode reports accurate counts
- Real run writes to all three ingestion tables
- No duplicates in `events`

## Phase 1 labeling

- [ ] Implement prompt loader with versioning
- [ ] Store labels with prompt hash + input hash
- [ ] Skip LLM when `has_description=false`

Definition of done:
- A run produces labels for at least 100 events
- Labels are stored append-only

## Phase 2 labeling

- [ ] Implement 9-category schema and validation
- [ ] Store labels in `event_phase2_labels`

Definition of done:
- Phase 2 labels join correctly in `v_bike_events`

## Ops

- [ ] Add GitHub Actions cron workflow
- [ ] Add run monitoring query examples

Definition of done:
- Cron workflow runs without overlap
- Failed runs are visible in `pipeline_runs`
