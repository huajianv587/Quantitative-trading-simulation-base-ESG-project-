create table if not exists quant_backtest_results (
    id uuid primary key default gen_random_uuid(),
    backtest_id text unique not null,
    strategy_name text not null,
    benchmark text not null,
    period_start date not null,
    period_end date not null,
    metrics jsonb not null default '{}'::jsonb,
    positions jsonb not null default '[]'::jsonb,
    timeline jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);
