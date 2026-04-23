-- Scheduler scan state persistence and lane-level scan job metadata.

CREATE TABLE IF NOT EXISTS scan_source_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lane VARCHAR(50) NOT NULL,
    source_key VARCHAR(100) NOT NULL,
    company_key VARCHAR(255) NOT NULL,
    checkpoint_value JSONB DEFAULT '{}'::jsonb,
    last_status VARCHAR(30) DEFAULT 'idle',
    blocked_reason TEXT,
    events_found INT DEFAULT 0,
    events_saved INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (lane, source_key, company_key)
);

CREATE INDEX IF NOT EXISTS idx_scan_source_state_lane_source
    ON scan_source_state (lane, source_key);

CREATE INDEX IF NOT EXISTS idx_scan_source_state_updated_at
    ON scan_source_state (updated_at DESC);

ALTER TABLE scan_jobs
    ADD COLUMN IF NOT EXISTS events_saved INT DEFAULT 0;

ALTER TABLE scan_jobs
    ADD COLUMN IF NOT EXISTS source_summary JSONB DEFAULT '{}'::jsonb;

ALTER TABLE scan_jobs
    ADD COLUMN IF NOT EXISTS blocked_reason TEXT;

ALTER TABLE scan_jobs
    ADD COLUMN IF NOT EXISTS next_actions JSONB DEFAULT '[]'::jsonb;

ALTER TABLE scan_jobs
    ADD COLUMN IF NOT EXISTS checkpoint_state JSONB DEFAULT '{}'::jsonb;

ALTER TABLE scan_source_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for scan source state" ON scan_source_state;
CREATE POLICY "Allow all for scan source state"
    ON scan_source_state FOR ALL USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS update_scan_source_state_updated_at ON scan_source_state;
CREATE TRIGGER update_scan_source_state_updated_at
    BEFORE UPDATE ON scan_source_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
