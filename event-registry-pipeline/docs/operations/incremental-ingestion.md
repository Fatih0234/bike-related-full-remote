# Incremental ingestion strategy

The Open311 API does not reliably return all recent events when queried only by
date. To avoid missing entries, incremental pulls must be driven by
`service_request_id` sequencing.

## Service request ID format

`service_request_id` is unique and encodes the sequence:

- `132-2025` = 132nd event in 2025
- `1231-2025` = 1231st event in 2025

The part before `-` is the sequence number. The part after `-` is the year.

## Algorithm (required)

1. Read the latest stored event for the active year from `events`:
   - `max(sequence_number)` where `year = current_year`.
2. Fetch a recent date window from the API to discover the latest available
   sequence for the same year (the maximum observed in that window).
3. If the API max sequence is higher than the stored sequence, fetch each
   missing ID directly (bounded by `INGESTION_GAP_FILL_LIMIT`):

   `/requests/{sequence}-{year}.json`

4. For each ID in the gap:
   - 200 -> ingest as normal
   - 404 -> record missing (deleted or never existed)
5. Update `pipeline_runs` with counts for fetched IDs and 404s.

## Example

- Last stored event: `34-2026`
- API shows newest: `100-2026`

Fetch and ingest IDs `35-2026` through `100-2026` directly.

This ensures all new events are captured, even when date-based queries omit
records. Use `INGESTION_ENABLE_GAP_FILL` to toggle and `INGESTION_GAP_FILL_LIMIT`
to cap the number of direct ID fetches per run.
