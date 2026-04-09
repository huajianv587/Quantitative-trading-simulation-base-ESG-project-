create table if not exists quant_factors (
    id uuid primary key default gen_random_uuid(),
    symbol text not null,
    factor_name text not null,
    factor_value numeric not null,
    contribution numeric,
    source text,
    observed_at timestamptz not null default now()
);

create index if not exists idx_quant_factors_symbol_observed_at
    on quant_factors(symbol, observed_at desc);
