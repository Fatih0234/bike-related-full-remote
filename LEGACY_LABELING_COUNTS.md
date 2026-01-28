# Legacy labeling coverage (checkpoint)

This note captures what was found in Supabase after migrating from `events_legacy` to the new
canonical + label-table schema.

## Counts

- `public.events_legacy`: **35,360** events total
- Legacy events with **any Phase 1 fields** present (`bike_related` OR `bike_confidence` OR `bike_reasoning` OR `bike_evidence`): **33,079**
- Legacy events with **no Phase 1 fields**: **2,281**
  - Of those, events with **no description**: **2,279**
  - The remaining **2** events have a description but no Phase 1 fields:
    - `26469-2025`
    - `16752-2025`

## Implication for the new pipeline

- Most historical Phase 1 work is already represented in `public.event_phase1_labels`.
- To avoid re-labeling the historical dataset, Phase 1/Phase 2 runners should default to selecting
  only events that have **no existing label rows** (any prompt version), and only label newly
  ingested/unlabeled events going forward.

