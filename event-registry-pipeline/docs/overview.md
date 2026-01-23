# Overview

This project ingests Cologne Open311 (Sag's uns) requests, normalizes them for
analysis, and applies two LLM labeling phases for bike-related insights.

## Pipeline stages

1. **Ingestion**
   - Fetch Open311 requests from the GeoReport API.
   - Store raw payloads in `events_raw` with a run ID.
   - Apply a quality gate and write rejects to `events_rejected`.
   - Upsert clean rows into `events`.

2. **Phase 1 labeling**
   - Classify events as bike-related or not.
   - Store outputs in `event_phase1_labels` (versioned, append-only).

3. **Phase 2 labeling**
   - Categorize bike-related events into issue types.
   - Store outputs in `event_phase2_labels` (versioned, append-only).

4. **Dashboards**
   - Analytics rely on stable views that join canonical events with the latest
     phase labels.

## Core tables

- `events_raw` - append-only API payloads with run metadata.
- `events_rejected` - quarantine with rejection reasons.
- `events` - canonical, deduplicated events for downstream use.
- `event_phase1_labels` - bike relevance outputs.
- `event_phase2_labels` - bike issue category outputs.
