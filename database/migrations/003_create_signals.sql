create table if not exists quant_signals (
    id uuid primary key default gen_random_uuid(),
    signal_id text unique not null,
    symbol text not null,
    company_name text not null,
    action text not null,
    confidence numeric not null,
    expected_return numeric not null,
    risk_score numeric not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
