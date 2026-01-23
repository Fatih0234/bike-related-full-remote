# GitHub Actions (planned)

## Cron strategy

- Schedule ingestion every 3h or 6h depending on API stability.
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

## Recommended steps

1. Checkout repo
2. Install uv
3. `uv sync`
4. `uv run erp ingest run --since ... --until ...`
5. Upload logs (if stored locally)
