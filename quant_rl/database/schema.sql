CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    artifacts_json TEXT NOT NULL
);
