-- Bootstrap schema aligned with the current database design

begin;

create extension if not exists cube;
create extension if not exists earthdistance;

create table if not exists public.pipeline_runs (
  run_id bigserial primary key,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  fetch_window_start timestamptz,
  fetch_window_end timestamptz,
  fetched_count int not null default 0,
  staged_count int not null default 0,
  inserted_count int not null default 0,
  updated_count int not null default 0,
  rejected_count int not null default 0,
  phase1_enqueued int not null default 0,
  phase2_enqueued int not null default 0,
  first_accepted_service_request_id varchar(20),
  last_accepted_service_request_id varchar(20),
  min_accepted_requested_at timestamptz,
  max_accepted_requested_at timestamptz,
  error_json jsonb
);

create table if not exists public.events_raw (
  raw_id bigserial primary key,
  run_id bigint not null references public.pipeline_runs(run_id),
  fetched_at timestamptz not null default now(),

  service_request_id varchar(20),
  title text,
  description text,
  requested_at timestamptz,
  status varchar(20),
  lat numeric(10,8),
  lon numeric(11,8),
  address_string text,
  service_name varchar(150),
  media_path varchar(500),

  payload jsonb not null
);

create index if not exists idx_events_raw_run_id on public.events_raw(run_id);
create index if not exists idx_events_raw_service_request_id on public.events_raw(service_request_id);
create index if not exists idx_events_raw_requested_at on public.events_raw(requested_at desc);

create table if not exists public.events_rejected (
  raw_id bigint primary key references public.events_raw(raw_id),
  run_id bigint not null references public.pipeline_runs(run_id),
  rejected_at timestamptz not null default now(),
  service_request_id varchar(20),
  accepted boolean not null default false,
  reject_reason text not null,
  reject_details jsonb
);

create index if not exists idx_events_rejected_run_id on public.events_rejected(run_id);
create index if not exists idx_events_rejected_reason on public.events_rejected(reject_reason);
create index if not exists idx_events_rejected_srid on public.events_rejected(service_request_id);
create index if not exists idx_events_rejected_accepted on public.events_rejected(accepted);

create table if not exists public.events (
  service_request_id varchar(20) primary key,

  title text not null,
  description text,
  description_redacted text,
  requested_at timestamptz not null,
  status varchar(20) not null check (status in ('open','closed')),

  lat numeric(10,8) not null,
  lon numeric(11,8) not null,
  address_string text not null,

  service_name varchar(150) not null,
  media_path varchar(500),

  category varchar(100) not null,
  subcategory varchar(150) not null,
  subcategory2 varchar(150),

  year smallint not null check (year between 2000 and 2100),
  sequence_number integer not null,

  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_run_id bigint references public.pipeline_runs(run_id),

  has_description boolean not null default false,
  has_media boolean not null default false,
  is_link_only boolean not null default false,
  is_flagged_abuse boolean not null default false,
  skip_llm boolean not null default false,

  constraint valid_coordinates check (
    lat >= -90 and lat <= 90 and lon >= -180 and lon <= 180
  )
);

create index if not exists idx_events_requested_at on public.events(requested_at desc);
create index if not exists idx_events_status on public.events(status);
create index if not exists idx_events_year on public.events(year);
create index if not exists idx_events_category on public.events(category);
create index if not exists idx_events_subcategory on public.events(subcategory);
create index if not exists idx_events_location on public.events using gist (
  ll_to_earth(lat::double precision, lon::double precision)
);

create table if not exists public.event_phase1_labels (
  label_id bigserial primary key,
  service_request_id varchar(20) not null references public.events(service_request_id),
  created_at timestamptz not null default now(),

  model text not null,
  prompt_version text not null,
  input_hash text not null,

  bike_related boolean,
  confidence numeric(3,2),
  evidence text[],
  reasoning text,

  unique(service_request_id, prompt_version, input_hash)
);

create index if not exists idx_p1_latest on public.event_phase1_labels(service_request_id, created_at desc);

create table if not exists public.event_phase2_labels (
  label_id bigserial primary key,
  service_request_id varchar(20) not null references public.events(service_request_id),
  created_at timestamptz not null default now(),

  model text not null,
  prompt_version text not null,
  input_hash text not null,

  bike_issue_category text,
  confidence numeric(3,2),
  evidence text[],
  reasoning text,

  unique(service_request_id, prompt_version, input_hash)
);

create index if not exists idx_p2_latest on public.event_phase2_labels(service_request_id, created_at desc);

create table if not exists public.labeling_runs (
  label_run_id bigserial primary key,
  phase text not null check (phase in ('phase1','phase2')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',

  model text not null,
  prompt_version text not null,
  dry_run boolean not null default false,
  requested_limit int,

  selected_count int not null default 0,
  attempted_count int not null default 0,
  inserted_count int not null default 0,
  skipped_count int not null default 0,
  failed_count int not null default 0,

  first_labeled_service_request_id varchar(20),
  last_labeled_service_request_id varchar(20),
  min_labeled_requested_at timestamptz,
  max_labeled_requested_at timestamptz,

  error_json jsonb
);

create index if not exists idx_labeling_runs_phase_started_at
  on public.labeling_runs(phase, started_at desc);
create index if not exists idx_labeling_runs_status_started_at
  on public.labeling_runs(status, started_at desc);
create index if not exists idx_labeling_runs_phase_prompt_started_at
  on public.labeling_runs(phase, prompt_version, started_at desc);

create or replace view public.v_bike_events as
with
p1 as (
  select distinct on (service_request_id)
    service_request_id,
    bike_related,
    confidence as bike_confidence,
    evidence as bike_evidence,
    reasoning as bike_reasoning,
    created_at as bike_labeled_at,
    model as bike_model,
    prompt_version as bike_prompt_version
  from public.event_phase1_labels
  order by service_request_id, created_at desc
),
p2 as (
  select distinct on (service_request_id)
    service_request_id,
    bike_issue_category,
    confidence as bike_issue_confidence,
    evidence as bike_issue_evidence,
    reasoning as bike_issue_reasoning,
    created_at as bike_issue_labeled_at,
    model as bike_issue_model,
    prompt_version as bike_issue_prompt_version
  from public.event_phase2_labels
  order by service_request_id, created_at desc
)
select
  e.service_request_id,
  e.requested_at,
  e.status,
  e.category,
  e.subcategory,
  e.subcategory2,
  e.service_name,
  e.address_string,
  e.title,
  e.description,
  e.media_path,
  e.lat::double precision as lat,
  e.lon::double precision as lon,
  e.year,
  e.sequence_number,

  p1.bike_related,
  p1.bike_confidence,
  p1.bike_evidence,
  p1.bike_reasoning,

  p2.bike_issue_category,
  p2.bike_issue_confidence,
  p2.bike_issue_evidence,
  p2.bike_issue_reasoning

from public.events e
left join p1 on p1.service_request_id = e.service_request_id
left join p2 on p2.service_request_id = e.service_request_id;

commit;
