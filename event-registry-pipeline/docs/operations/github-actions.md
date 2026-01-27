# GitHub Actions

## Cron strategy

- Schedule ingestion every 6h (start conservative; tighten later if needed).
- Schedule labeling every 6h (offset) to avoid overlap with ingestion.
- Use a single workflow with a concurrency group to avoid overlap.
- Always write `pipeline_runs` for observability.

## Secrets

Store the following in GitHub Actions secrets:
- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (if needed)
- `GOOGLE_API_KEY` (when labeling)
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (optional)

## Concurrency

```yaml
concurrency:
  group: ingest-cron
  cancel-in-progress: true
```

Labeling uses a separate group:

```yaml
concurrency:
  group: label-cron
  cancel-in-progress: true
```

## Recommended steps

1. Checkout repo
2. Install uv
3. `cd event-registry-pipeline && uv sync`
4. `cd event-registry-pipeline && uv run erp ingest auto`
5. `cd event-registry-pipeline && uv run erp phase1 run --limit 500`
6. `cd event-registry-pipeline && uv run erp phase2 run --limit 500`
7. Upload logs (if stored locally)

## Notes on date windows

The Open311 endpoint is date-based. For “include today”, `erp ingest auto` sets:
- `until = tomorrow` (UTC date + 1 day)
- `since = last successful run’s fetch_window_end` (or a small fallback lookback)

You can also run manual windows via `erp ingest run --since ... --until ...`.
