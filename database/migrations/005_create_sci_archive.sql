create table if not exists sci_archive (
    id uuid primary key default gen_random_uuid(),
    artifact_type text not null,
    artifact_key text unique not null,
    title text not null,
    summary text,
    payload jsonb not null default '{}'::jsonb,
    artifact_uri text,
    created_at timestamptz not null default now()
);

create table if not exists quant_run_registry (
    id uuid primary key default gen_random_uuid(),
    run_id text unique not null,
    run_type text not null,
    payload jsonb not null default '{}'::jsonb,
    artifact_uri text,
    created_at timestamptz
);
