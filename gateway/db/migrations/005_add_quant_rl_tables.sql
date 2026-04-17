create table if not exists quant_rl_runs (
    run_id text primary key,
    created_at text not null,
    algorithm text not null,
    phase text not null,
    status text not null,
    config_json text,
    metrics_json text,
    artifacts_json text
);

create table if not exists quant_rl_backtests (
    run_id text primary key,
    created_at text not null,
    algorithm text not null,
    metrics_json text,
    artifacts_json text
);

create table if not exists quant_rl_policies (
    policy_id text primary key,
    created_at text not null,
    algorithm text not null,
    phase text not null,
    checkpoint_uri text not null,
    status text not null,
    notes text
);
