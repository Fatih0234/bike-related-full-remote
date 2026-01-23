# Agent brief

This repo is intentionally scaffolded. Follow these rules when extending it.

## Safe starting points

- Read `docs/architecture.md` and `docs/database/schema.md` first.
- Check `docs/legacy/` for historical API and prompt behavior.

## Do not touch

- Do not edit legacy repos under `/Volumes/T7/eventRegistryApi` or
  `/Volumes/T7/flag-the-event`.
- Do not commit secrets. `.env` is always local only.

## Config locations

- Environment variables: `.env` (template in `.env.example`).
- Category mapping CSV: `data/sags_uns_categories_3level.csv`.
- Prompts: `prompts/phase1/` and `prompts/phase2/`.

## Ingestion rules to follow

- Always write API payloads to `events_raw` first.
- Use the quality gate to decide `events` vs `events_rejected`.
- Never write LLM outputs into `events`.

## Incremental pull logic (critical)

Date windows alone miss new API entries. The ingestion runner must:

1. Determine the last stored `sequence_number` for the active year.
2. Fetch a recent window to discover the current max sequence.
3. Fetch missing IDs with `/requests/{id}.json` for the range
   `(last_sequence + 1) .. max_sequence`.
4. Treat 404s as deleted; record in run metrics.

Example: last stored = `34-2026`, latest seen = `100-2026`.
Fetch IDs `35-2026` through `100-2026` directly.

See `docs/operations/incremental-ingestion.md` for the full algorithm.

## How to run tests/lint

```bash
uv run pytest
uv run ruff check .
```

## Prompt versioning

- Create a new versioned file (e.g., `v002.md`) in the prompt folder.
- Keep old prompt files unchanged for reproducibility.
- Record prompt hash + input hash in label tables.
