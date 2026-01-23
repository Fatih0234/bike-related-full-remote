# Legacy notes: flag-the-event

## Prompt versioning

- Prompts are stored under `prompts/phase1/` and `phase2/prompts/` with
  zero-padded versions (`v001.md`, `v002.md`).
- Prompt changes never overwrite previous versions.
- Prompt hash is recorded with every run for reproducibility.

## Output schema conventions

- Phase 1 output JSON includes `label`, `evidence`, `reasoning`, `confidence`.
- Phase 2 output JSON includes `category`, `evidence`, `reasoning`, `confidence`.
- Both phases require strict JSON validation with a retry/repair prompt when
  validation fails.

## Run artifacts

- Runs are stored in `runs/<timestamp>_v###_model/` with
  `predictions.jsonl`, `metrics.json`, `config.json`, `errors.jsonl`.
- Misclassification reports are generated as markdown for analysis.

## LLM control rules

- Skip labeling when descriptions are empty or missing.
- Use category prefilters (service_name) to avoid unnecessary LLM calls.
- Legacy sets included:
  - DEFINITELY_EXCLUDE: containers, lighting, graffiti, parks, abandoned bikes
  - HIGH_POTENTIAL: defekte oberflaeche, strassenmarkierung, radfahrerampel
  - MEDIUM_POTENTIAL: wilder muell, gully verstopft, ampel issues

## Tracing

- Langfuse is optional but used for tracing model calls when configured.

## Environment variables

- GOOGLE_API_KEY
- LANGFUSE_PUBLIC_KEY
- LANGFUSE_SECRET_KEY
- LANGFUSE_HOST
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
