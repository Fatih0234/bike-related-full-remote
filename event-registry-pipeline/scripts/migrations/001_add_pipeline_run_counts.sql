alter table pipeline_runs
    add column if not exists inserted_count integer,
    add column if not exists updated_count integer;
