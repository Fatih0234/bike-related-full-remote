alter table events
    add column if not exists has_media boolean default false,
    add column if not exists is_link_only boolean default false;
