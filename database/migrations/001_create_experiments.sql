create table if not exists quant_experiments (
    id uuid primary key default gen_random_uuid(),
    experiment_id text unique not null,
    name text not null,
    objective text not null,
    benchmark text not null,
    metrics jsonb not null default '{}'::jsonb,
    tags jsonb not null default '[]'::jsonb,
    artifact_uri text,
    created_at timestamptz not null default now()
);
