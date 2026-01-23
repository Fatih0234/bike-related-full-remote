# Legacy notes: eventRegistryApi

## API behavior

- Base URL: `https://sags-uns.stadt-koeln.de/georeport/v2`
- List endpoint: `/requests.json`
- Single record endpoint: `/requests/{service_request_id}.json`
- Known issue: date-range queries miss ~20% of records.

### Pagination pattern

- Uses `page` parameter with `start_date`, `end_date`, `extensions=true`.
- Stop when an empty page is returned or page size < 100.

### Gap fill strategy (critical)

1. Fetch by date windows to collect most IDs.
2. Determine missing IDs by year and sequence.
3. Request each missing ID directly via `/requests/{id}.json`.
4. 404 means the record was deleted or never existed.

## Data enrichment

- Category mapping uses `sags_uns_categories_3level.csv` (service_name ->
  category/subcategory/subcategory2).
- Address parsing relies on regex; malformed addresses are allowed with NULL
  components.
- `media_path` is stored as the relative path after `/files/` to reduce storage.
- `year` and `sequence_number` are derived from `service_request_id`.
- No title-based sequence parsing was used in legacy code.

## Storage strategy

- Raw fetches were stored in `all_events.json` on disk.
- A single `events` table was populated via batch inserts.
- Migrations lived under `migrations/` with manual SQL execution.

## Environment variables

- SUPABASE_URL
- SUPABASE_KEY
- GEMINI_API_KEY (used in earlier experiments)

## Implications for new pipeline

- Do not rely on timestamps alone for incremental pulls.
- Preserve `service_request_id` ordering to fill gaps.
- Keep category enrichment logic driven by the CSV mapping file.
