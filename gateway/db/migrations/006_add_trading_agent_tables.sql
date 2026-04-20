create table if not exists watchlist (
    watchlist_id text primary key,
    symbol text not null,
    added_date text not null,
    esg_score double precision,
    last_sentiment double precision,
    enabled boolean not null default true,
    note text,
    metadata jsonb,
    storage jsonb,
    updated_at text
);

create index if not exists idx_watchlist_symbol on watchlist(symbol);
create index if not exists idx_watchlist_enabled on watchlist(enabled);

create table if not exists price_alerts (
    alert_id text primary key,
    timestamp text not null,
    symbol text not null,
    trigger_type text not null,
    trigger_value double precision not null,
    threshold double precision not null,
    agent_analysis text,
    debate_id text,
    risk_decision text,
    execution_id text,
    metadata jsonb,
    storage jsonb
);

create index if not exists idx_price_alerts_symbol_timestamp on price_alerts(symbol, timestamp desc);

create table if not exists debate_runs (
    debate_id text primary key,
    generated_at text not null,
    symbol text not null,
    universe jsonb,
    bull_thesis text,
    bear_thesis text,
    turns jsonb,
    conflict_points jsonb,
    consensus_points jsonb,
    judge_verdict text not null,
    judge_confidence double precision,
    dispute_score double precision,
    recommended_action text,
    confidence_shift double precision,
    requires_human_review boolean not null default false,
    evidence_run_id text,
    factor_count integer,
    sentiment_snapshot_id text,
    expected_edge double precision,
    metadata jsonb,
    lineage jsonb,
    storage jsonb
);

create index if not exists idx_debate_runs_symbol_generated_at on debate_runs(symbol, generated_at desc);

create table if not exists risk_approvals (
    approval_id text primary key,
    generated_at text not null,
    symbol text not null,
    debate_id text,
    requested_action text not null,
    approved_action text not null,
    verdict text not null,
    kelly_fraction double precision,
    recommended_weight double precision,
    recommended_notional double precision,
    max_position_weight double precision,
    drawdown_estimate double precision,
    signal_ttl_minutes integer,
    duplicate_order_detected boolean not null default false,
    market_open boolean,
    hard_blocks jsonb,
    risk_flags jsonb,
    rationale jsonb,
    account_snapshot jsonb,
    positions_snapshot jsonb,
    metadata jsonb,
    lineage jsonb,
    storage jsonb
);

create index if not exists idx_risk_approvals_symbol_generated_at on risk_approvals(symbol, generated_at desc);

create table if not exists daily_reviews (
    review_id text primary key,
    review_date text not null,
    generated_at text not null,
    pnl double precision,
    trades_count integer,
    esg_signals jsonb,
    approved_decisions integer,
    blocked_decisions integer,
    report_text text not null,
    strategy_effectiveness jsonb,
    next_day_risk_flags jsonb,
    metadata jsonb,
    lineage jsonb,
    storage jsonb
);

create index if not exists idx_daily_reviews_generated_at on daily_reviews(generated_at desc);

create table if not exists scheduler_job_runs (
    run_id text primary key,
    job_name text not null,
    scheduled_for text not null,
    started_at text not null,
    completed_at text,
    status text not null,
    auto_submit_triggered boolean not null default false,
    market_day boolean not null default true,
    error text,
    result_ref jsonb,
    storage jsonb
);

create index if not exists idx_scheduler_job_runs_name_started on scheduler_job_runs(job_name, started_at desc);
