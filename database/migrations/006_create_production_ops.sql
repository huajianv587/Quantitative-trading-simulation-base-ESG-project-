create extension if not exists pgcrypto;

create table if not exists strategy_registry (
    id uuid primary key default gen_random_uuid(),
    strategy_id text not null,
    name text,
    status text not null default 'active',
    symbol text,
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists strategy_registry_strategy_id_uidx on strategy_registry (strategy_id);
create index if not exists strategy_registry_status_idx on strategy_registry (status);
create index if not exists strategy_registry_updated_at_idx on strategy_registry (updated_at desc);

create table if not exists strategy_allocations (
    id uuid primary key default gen_random_uuid(),
    allocation_id text not null,
    strategy_id text not null,
    capital_allocation numeric,
    max_symbols integer,
    status text not null default 'active',
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists strategy_allocations_allocation_id_uidx on strategy_allocations (allocation_id);
create unique index if not exists strategy_allocations_strategy_id_uidx on strategy_allocations (strategy_id);
create index if not exists strategy_allocations_updated_at_idx on strategy_allocations (updated_at desc);

create table if not exists autopilot_policies (
    id uuid primary key default gen_random_uuid(),
    policy_id text not null,
    requested_mode text not null default 'paper',
    effective_mode text not null default 'paper',
    auto_submit_enabled boolean not null default false,
    armed boolean not null default false,
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists autopilot_policies_policy_id_uidx on autopilot_policies (policy_id);
create index if not exists autopilot_policies_generated_at_idx on autopilot_policies (generated_at desc);

create table if not exists debate_runs (
    id uuid primary key default gen_random_uuid(),
    debate_id text not null,
    symbol text,
    status text not null default 'completed',
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists debate_runs_debate_id_uidx on debate_runs (debate_id);
create index if not exists debate_runs_symbol_generated_idx on debate_runs (symbol, generated_at desc);

create table if not exists daily_reviews (
    id uuid primary key default gen_random_uuid(),
    review_id text not null,
    session_date date,
    status text not null default 'completed',
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists daily_reviews_review_id_uidx on daily_reviews (review_id);
create index if not exists daily_reviews_session_date_idx on daily_reviews (session_date desc);

create table if not exists paper_performance_snapshots (
    id uuid primary key default gen_random_uuid(),
    snapshot_id text not null,
    session_date date,
    status text not null default 'completed',
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists paper_performance_snapshots_snapshot_id_uidx on paper_performance_snapshots (snapshot_id);
create index if not exists paper_performance_snapshots_session_idx on paper_performance_snapshots (session_date desc);

create table if not exists paper_outcomes (
    id uuid primary key default gen_random_uuid(),
    outcome_id text not null,
    symbol text,
    status text not null default 'open',
    record_kind text,
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists paper_outcomes_outcome_id_uidx on paper_outcomes (outcome_id);
create index if not exists paper_outcomes_status_symbol_idx on paper_outcomes (status, symbol);

create table if not exists session_evidence (
    id uuid primary key default gen_random_uuid(),
    session_date date not null,
    status text not null default 'degraded',
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists session_evidence_session_date_uidx on session_evidence (session_date);
create index if not exists session_evidence_updated_at_idx on session_evidence (updated_at desc);

create table if not exists scheduler_events (
    id uuid primary key default gen_random_uuid(),
    event_id text not null,
    session_date date,
    stage text,
    status text not null default 'completed',
    payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists scheduler_events_event_id_uidx on scheduler_events (event_id);
create index if not exists scheduler_events_stage_status_idx on scheduler_events (stage, status, generated_at desc);

create table if not exists submit_locks (
    id uuid primary key default gen_random_uuid(),
    lock_key text,
    lock_id text,
    session_date date,
    strategy_id text,
    symbol text,
    side text,
    status text not null default 'acquired',
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists submit_locks_lock_key_uidx on submit_locks (lock_key) where lock_key is not null;
create unique index if not exists submit_locks_lock_id_uidx on submit_locks (lock_id) where lock_id is not null;
create index if not exists submit_locks_session_status_idx on submit_locks (session_date desc, status);

create table if not exists quant_jobs (
    id uuid primary key default gen_random_uuid(),
    job_id text not null,
    job_type text not null,
    status text not null check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'degraded', 'blocked')),
    payload jsonb not null default '{}'::jsonb,
    result jsonb,
    error text,
    logs jsonb not null default '[]'::jsonb,
    events jsonb not null default '[]'::jsonb,
    attempt integer not null default 1,
    acceptance_namespace text,
    queued_at timestamptz,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists quant_jobs_job_id_uidx on quant_jobs (job_id);
create index if not exists quant_jobs_status_type_idx on quant_jobs (status, job_type, created_at desc);
create index if not exists quant_jobs_namespace_idx on quant_jobs (acceptance_namespace, created_at desc);

create table if not exists quant_job_events (
    id uuid primary key default gen_random_uuid(),
    event_id text not null,
    job_id text not null,
    event_type text not null,
    status text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create unique index if not exists quant_job_events_event_id_uidx on quant_job_events (event_id);
create index if not exists quant_job_events_job_id_idx on quant_job_events (job_id, created_at asc);

create table if not exists data_source_configs (
    id uuid primary key default gen_random_uuid(),
    provider_id text not null,
    priority integer not null default 100,
    status text not null default 'configured',
    payload jsonb not null default '{}'::jsonb,
    acceptance_namespace text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists data_source_configs_provider_id_uidx on data_source_configs (provider_id);
create index if not exists data_source_configs_priority_idx on data_source_configs (priority asc, provider_id asc);

create table if not exists provider_health_checks (
    id uuid primary key default gen_random_uuid(),
    check_id text not null,
    provider_id text not null,
    status text not null default 'degraded',
    payload jsonb not null default '{}'::jsonb,
    checked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists provider_health_checks_check_id_uidx on provider_health_checks (check_id);
create index if not exists provider_health_checks_provider_idx on provider_health_checks (provider_id, checked_at desc);

create table if not exists data_quality_runs (
    id uuid primary key default gen_random_uuid(),
    run_id text not null,
    dataset_id text,
    provider_id text,
    status text not null default 'degraded',
    quality_score numeric,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create unique index if not exists data_quality_runs_run_id_uidx on data_quality_runs (run_id);
create index if not exists data_quality_runs_dataset_idx on data_quality_runs (dataset_id, created_at desc);
