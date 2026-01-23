# Database migrations

This project uses SQL-first migrations. For now, the bootstrap schema lives in
`scripts/bootstrap_db.sql` and can be applied in Supabase SQL Editor or via a
direct Postgres connection.

## Apply bootstrap schema

```bash
# From the project root
psql "$DATABASE_URL" -f scripts/bootstrap_db.sql
```

## Migration workflow (planned)

1. Create new migration under `migrations/` with a numeric prefix.
2. Apply migrations in order in the Supabase SQL editor or via CI.
3. Record changes in `docs/planning/decisions.md` when schema decisions change.
