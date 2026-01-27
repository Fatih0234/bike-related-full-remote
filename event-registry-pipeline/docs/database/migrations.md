# Database migrations

This project uses SQL-first migrations. For now, the bootstrap schema lives in
`scripts/bootstrap_db.sql` and can be applied in Supabase SQL Editor or via a
direct Postgres connection.

## Apply bootstrap schema

```bash
# From the project root
psql "$DATABASE_URL" -f scripts/bootstrap_db.sql
```

## Incremental migrations

If your database already uses the expanded schema (raw/rejected/canonical +
labels), you may need to apply incremental migration scripts. The files in
`scripts/migrations/` add columns and indexes that may be missing in older schemas.

### Migration list

| Migration | Description |
|-----------|-------------|
| `001_add_pipeline_run_counts.sql` | Adds `inserted_count` and `updated_count` to `pipeline_runs` |
| `002_add_event_flags.sql` | Adds `has_media` and `is_link_only` to `events` |
| `003_add_events_rejected_srid.sql` | Adds `service_request_id` column to `events_rejected` for easier debugging |
| `006_add_events_rejected_accepted.sql` | Adds `accepted` flag to `events_rejected` to separate rejects vs warnings |
| `007_add_pipeline_run_ranges.sql` | Adds first/last accepted IDs + min/max accepted requested_at to `pipeline_runs` |

### Apply migrations

```bash
# Apply all migrations in order
psql "$DATABASE_URL" -f scripts/migrations/001_add_pipeline_run_counts.sql
psql "$DATABASE_URL" -f scripts/migrations/002_add_event_flags.sql
psql "$DATABASE_URL" -f scripts/migrations/003_add_events_rejected_srid.sql
psql "$DATABASE_URL" -f scripts/migrations/006_add_events_rejected_accepted.sql
psql "$DATABASE_URL" -f scripts/migrations/007_add_pipeline_run_ranges.sql
```

## Migration workflow (planned)

1. Create new migration under `migrations/` with a numeric prefix.
2. Apply migrations in order in the Supabase SQL editor or via CI.
3. Record changes in `docs/planning/decisions.md` when schema decisions change.
