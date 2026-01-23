-- Bootstrap schema for Event Registry Pipeline

create extension if not exists "pgcrypto";

create table if not exists pipeline_runs (
    run_id uuid primary key default gen_random_uuid(),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    status text not null default 'running',
    fetch_window_start date,
    fetch_window_end date,
    fetched_count integer,
    raw_inserted_count integer,
    rejected_count integer,
    canonical_upserted_count integer,
    missing_id_404_count integer,
    error_json jsonb
);

create table if not exists events_raw (
    raw_id bigserial primary key,
    run_id uuid references pipeline_runs(run_id),
    service_request_id text,
    title text,
    description text,
    requested_at timestamptz,
    status text,
    lat double precision,
    lon double precision,
    address_string text,
    service_name text,
    media_url text,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists events_rejected (
    reject_id bigserial primary key,
    run_id uuid references pipeline_runs(run_id),
    raw_id bigint references events_raw(raw_id),
    service_request_id text,
    reject_reason text not null,
    reject_details jsonb,
    created_at timestamptz not null default now()
);

create table if not exists events (
    service_request_id text primary key,
    title text,
    description text,
    requested_at timestamptz,
    status text,
    lat double precision,
    lon double precision,
    address_string text,
    service_name text,
    category text,
    subcategory text,
    subcategory2 text,
    media_path text,
    year integer,
    sequence_number integer,
    has_description boolean default false,
    skip_llm boolean default false,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    last_run_id uuid references pipeline_runs(run_id)
);

create index if not exists idx_events_requested_at on events (requested_at);
create index if not exists idx_events_status on events (status);
create index if not exists idx_events_category on events (category);
create index if not exists idx_events_year_seq on events (year, sequence_number);

create table if not exists event_phase1_labels (
    label_id bigserial primary key,
    service_request_id text references events(service_request_id),
    prompt_version text not null,
    model_id text not null,
    input_hash text not null,
    label text not null,
    confidence numeric,
    evidence jsonb,
    reasoning text,
    created_at timestamptz not null default now(),
    unique (service_request_id, prompt_version, input_hash)
);

create table if not exists event_phase2_labels (
    label_id bigserial primary key,
    service_request_id text references events(service_request_id),
    prompt_version text not null,
    model_id text not null,
    input_hash text not null,
    category text not null,
    confidence numeric,
    evidence jsonb,
    reasoning text,
    created_at timestamptz not null default now(),
    unique (service_request_id, prompt_version, input_hash)
);

create or replace view v_bike_events as
select
    e.*,
    p1.label as phase1_label,
    p1.confidence as phase1_confidence,
    p1.prompt_version as phase1_prompt_version,
    p1.model_id as phase1_model_id,
    p1.created_at as phase1_created_at,
    p2.category as phase2_category,
    p2.confidence as phase2_confidence,
    p2.prompt_version as phase2_prompt_version,
    p2.model_id as phase2_model_id,
    p2.created_at as phase2_created_at
from events e
left join lateral (
    select label, confidence, prompt_version, model_id, created_at
    from event_phase1_labels
    where service_request_id = e.service_request_id
    order by created_at desc
    limit 1
) p1 on true
left join lateral (
    select category, confidence, prompt_version, model_id, created_at
    from event_phase2_labels
    where service_request_id = e.service_request_id
    order by created_at desc
    limit 1
) p2 on true;
