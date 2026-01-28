# GitHub Actions

## Orchestration strategy

- `ingest-cron` runs on a 6h schedule.
- `phase1` runs automatically after a successful `ingest-cron`.
- `phase2` runs automatically after a successful `phase1`.
- Each workflow has its own `concurrency` group to avoid overlapping runs.

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

Phase 1 and Phase 2 each use their own group:

```yaml
concurrency:
  group: phase1
  cancel-in-progress: true
```

```yaml
concurrency:
  group: phase2
  cancel-in-progress: true
```

## Recommended steps

1. Checkout repo
2. Install uv
3. `cd event-registry-pipeline && uv sync`
4. `cd event-registry-pipeline && uv run erp ingest auto`
5. `cd event-registry-pipeline && uv run erp phase1 run --limit 1000`
6. `cd event-registry-pipeline && uv run erp phase2 run --limit 1000`
7. Upload logs (if stored locally)

## Notes on date windows

The Open311 endpoint is date-based. For “include today”, `erp ingest auto` sets:
- `until = tomorrow` (UTC date + 1 day)
- `since = last successful run’s fetch_window_end` (or a small fallback lookback)

You can also run manual windows via `erp ingest run --since ... --until ...`.
