-- Migration 003: Add service_request_id to events_rejected
-- This column allows easier debugging of rejected records without joining to events_raw

alter table public.events_rejected
add column if not exists service_request_id varchar(20);

create index if not exists idx_events_rejected_srid
on public.events_rejected(service_request_id);
