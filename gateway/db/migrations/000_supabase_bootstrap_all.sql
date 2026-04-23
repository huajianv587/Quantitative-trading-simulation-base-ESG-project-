-- Consolidated Supabase bootstrap for this project.
-- Run the whole file once in Supabase SQL Editor for a fresh project.
-- Preferred backend credential after setup: SUPABASE_SERVICE_ROLE_KEY

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Shared helper function
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 001_init_sessions.sql
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT UNIQUE NOT NULL,
    user_id    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id
    ON sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at
    ON sessions (created_at DESC);

CREATE TABLE IF NOT EXISTS chat_history (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL
               REFERENCES sessions (session_id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_session_created
    ON chat_history (session_id, created_at);

-- ---------------------------------------------------------------------------
-- 002_add_esg_report_tables.sql
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS esg_reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type  VARCHAR(20) NOT NULL,
    title        VARCHAR(255) NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end   TIMESTAMP NOT NULL,
    data         JSONB NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (report_type, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_report_type_date
    ON esg_reports (report_type, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_period
    ON esg_reports (period_start, period_end);

CREATE TABLE IF NOT EXISTS company_data_snapshot (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name      VARCHAR(255) NOT NULL,
    ticker            VARCHAR(10),
    industry          VARCHAR(100),
    esg_score_report  JSONB,
    financial_metrics JSONB,
    external_ratings  JSONB,
    snapshot_date     DATE NOT NULL,
    last_updated      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (company_name, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_company_date
    ON company_data_snapshot (company_name, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_snapshot_date
    ON company_data_snapshot (snapshot_date);

CREATE TABLE IF NOT EXISTS report_push_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id     UUID NOT NULL REFERENCES esg_reports (id) ON DELETE CASCADE,
    user_id       VARCHAR(255) NOT NULL,
    push_channels TEXT[] NOT NULL,
    push_status   VARCHAR(20) NOT NULL DEFAULT 'pending',
    delivered_at  TIMESTAMP,
    read_at       TIMESTAMP,
    click_through BOOLEAN DEFAULT FALSE,
    feedback_score INT CHECK (feedback_score >= 1 AND feedback_score <= 5),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (report_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_push
    ON report_push_history (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_report_push
    ON report_push_history (report_id, push_status);

CREATE INDEX IF NOT EXISTS idx_push_status
    ON report_push_history (push_status);

CREATE TABLE IF NOT EXISTS push_rules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name     VARCHAR(255) NOT NULL UNIQUE,
    condition     TEXT NOT NULL,
    target_users  VARCHAR(50) NOT NULL,
    push_channels TEXT[] NOT NULL,
    priority      INT NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    template_id   VARCHAR(255) NOT NULL,
    enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enabled_priority
    ON push_rules (enabled, priority DESC);

CREATE INDEX IF NOT EXISTS idx_target_users
    ON push_rules (target_users);

CREATE TABLE IF NOT EXISTS user_report_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(255) NOT NULL,
    report_types    TEXT[] NOT NULL,
    companies       TEXT[] NOT NULL,
    alert_threshold JSONB NOT NULL,
    push_channels   TEXT[] NOT NULL,
    frequency       VARCHAR(50) NOT NULL DEFAULT 'daily',
    subscribed_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions
    ON user_report_subscriptions (user_id);

CREATE INDEX IF NOT EXISTS idx_frequency
    ON user_report_subscriptions (frequency);

CREATE TABLE IF NOT EXISTS push_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    push_history_id UUID NOT NULL REFERENCES report_push_history (id) ON DELETE CASCADE,
    user_id         VARCHAR(255) NOT NULL,
    rating          INT CHECK (rating >= 1 AND rating <= 5),
    feedback_text   TEXT,
    action_taken    VARCHAR(50),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_feedback
    ON push_feedback (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_rating
    ON push_feedback (rating);

CREATE OR REPLACE VIEW report_push_statistics AS
SELECT
    rph.report_id,
    COUNT(*) AS total_pushed,
    COUNT(CASE WHEN rph.delivered_at IS NOT NULL THEN 1 END) AS delivered_count,
    COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) AS read_count,
    COUNT(CASE WHEN rph.click_through THEN 1 END) AS click_count,
    ROUND(
        100.0 * COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0),
        2
    ) AS read_rate,
    ROUND(
        100.0 * COUNT(CASE WHEN rph.click_through THEN 1 END) / NULLIF(COUNT(*), 0),
        2
    ) AS ctr,
    AVG(CASE WHEN rph.feedback_score IS NOT NULL THEN rph.feedback_score ELSE 0 END) AS avg_feedback_score
FROM report_push_history rph
GROUP BY rph.report_id;

CREATE OR REPLACE VIEW user_push_activity AS
SELECT
    rph.user_id,
    COUNT(*) AS total_pushed,
    COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) AS read_count,
    COUNT(CASE WHEN rph.click_through THEN 1 END) AS click_count,
    MAX(rph.delivered_at) AS last_push_date,
    ROUND(
        100.0 * COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0),
        2
    ) AS engagement_rate
FROM report_push_history rph
WHERE rph.created_at >= NOW() - INTERVAL '30 days'
GROUP BY rph.user_id;

ALTER TABLE esg_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_data_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_push_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_report_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for esg_reports" ON esg_reports;
CREATE POLICY "Allow all for esg_reports"
    ON esg_reports FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for company_data_snapshot" ON company_data_snapshot;
CREATE POLICY "Allow all for company_data_snapshot"
    ON company_data_snapshot FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Users can view own push history" ON report_push_history;
CREATE POLICY "Users can view own push history"
    ON report_push_history FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Users can manage own subscriptions" ON user_report_subscriptions;
CREATE POLICY "Users can manage own subscriptions"
    ON user_report_subscriptions FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for push_rules" ON push_rules;
CREATE POLICY "Allow all for push_rules"
    ON push_rules FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for push_feedback" ON push_feedback;
CREATE POLICY "Allow all for push_feedback"
    ON push_feedback FOR ALL USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS update_push_rules_updated_at ON push_rules;
CREATE TRIGGER update_push_rules_updated_at
    BEFORE UPDATE ON push_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_report_subscriptions_updated_at ON user_report_subscriptions;
CREATE TRIGGER update_user_report_subscriptions_updated_at
    BEFORE UPDATE ON user_report_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

INSERT INTO push_rules (
    rule_name,
    condition,
    target_users,
    push_channels,
    priority,
    template_id,
    enabled
)
VALUES
    ('warn_low_esg', 'low_performer_count > 0', 'holders', ARRAY['email', 'in_app'], 8, 'template_low_esg_warning', true),
    ('highlight_excellence', 'high_performer_count > 0', 'all', ARRAY['in_app'], 5, 'template_excellence', true),
    ('critical_risk_alert', 'overall_score < 30', 'analysts', ARRAY['email', 'webhook'], 10, 'template_critical_alert', true)
ON CONFLICT (rule_name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 003_add_scheduler_tables.sql
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    VARCHAR(255) UNIQUE NOT NULL,
    email      VARCHAR(255),
    name       VARCHAR(255),
    role       VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email
    ON users (email);

CREATE TABLE IF NOT EXISTS user_holdings (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      VARCHAR(255) NOT NULL,
    company      VARCHAR(255),
    company_name VARCHAR(255) NOT NULL,
    ticker       VARCHAR(20),
    shares       DECIMAL(18,4),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, company_name)
);

CREATE INDEX IF NOT EXISTS idx_holdings_user
    ON user_holdings (user_id);

CREATE TABLE IF NOT EXISTS user_preferences (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               VARCHAR(255) UNIQUE NOT NULL,
    watched_companies     TEXT[],
    interested_companies  TEXT[],
    interested_categories TEXT[] DEFAULT ARRAY['E', 'S', 'G'],
    watched_industries    TEXT[],
    risk_threshold        VARCHAR(20) DEFAULT 'medium',
    keywords              TEXT[] DEFAULT ARRAY[]::TEXT[],
    notification_channels TEXT[] DEFAULT ARRAY['in_app'],
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prefs_user
    ON user_preferences (user_id);

CREATE TABLE IF NOT EXISTS esg_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      VARCHAR(100) NOT NULL,
    source_url  TEXT,
    title       VARCHAR(500),
    description TEXT,
    content     TEXT,
    company     VARCHAR(255),
    event_type  VARCHAR(50),
    raw_content TEXT,
    raw_data    JSONB,
    detected_at TIMESTAMPTZ,
    scanned_at  TIMESTAMPTZ DEFAULT NOW(),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_company
    ON esg_events (company);

CREATE INDEX IF NOT EXISTS idx_events_type
    ON esg_events (event_type);

CREATE INDEX IF NOT EXISTS idx_events_scanned
    ON esg_events (scanned_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_detected
    ON esg_events (detected_at DESC);

CREATE TABLE IF NOT EXISTS extracted_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_event_id UUID REFERENCES esg_events (id) ON DELETE SET NULL,
    raw_event_id      UUID REFERENCES esg_events (id) ON DELETE SET NULL,
    title             VARCHAR(500) NOT NULL,
    description       TEXT,
    company           VARCHAR(255),
    event_type        VARCHAR(50),
    impact_area       VARCHAR(20),
    severity          VARCHAR(20),
    risk_level        VARCHAR(20),
    key_metrics       JSONB,
    affected_areas    TEXT[],
    extracted_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extracted_company
    ON extracted_events (company);

CREATE INDEX IF NOT EXISTS idx_extracted_risk
    ON extracted_events (risk_level);

CREATE INDEX IF NOT EXISTS idx_extracted_created
    ON extracted_events (created_at DESC);

CREATE TABLE IF NOT EXISTS risk_scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID REFERENCES extracted_events (id) ON DELETE CASCADE,
    risk_level          VARCHAR(20) NOT NULL,
    score               INT CHECK (score >= 0 AND score <= 100),
    reasoning           TEXT,
    affected_dimensions JSONB,
    recommendation      TEXT,
    recommendations     TEXT[],
    scored_at           TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_event
    ON risk_scores (event_id);

CREATE INDEX IF NOT EXISTS idx_risk_level
    ON risk_scores (risk_level);

CREATE INDEX IF NOT EXISTS idx_risk_score
    ON risk_scores (score DESC);

CREATE TABLE IF NOT EXISTS event_user_matches (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id     UUID REFERENCES extracted_events (id) ON DELETE CASCADE,
    user_id      VARCHAR(255) NOT NULL,
    match_reason TEXT,
    relevance    DECIMAL(5,2),
    matched_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_match_user
    ON event_user_matches (user_id);

CREATE INDEX IF NOT EXISTS idx_match_event
    ON event_user_matches (event_id);

CREATE TABLE IF NOT EXISTS scan_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type     VARCHAR(50) NOT NULL,
    status       VARCHAR(20) DEFAULT 'pending',
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    events_found INT DEFAULT 0,
    events_saved INT DEFAULT 0,
    error_msg    TEXT,
    source_summary JSONB DEFAULT '{}'::jsonb,
    blocked_reason TEXT,
    next_actions JSONB DEFAULT '[]'::jsonb,
    checkpoint_state JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_status
    ON scan_jobs (status);

CREATE INDEX IF NOT EXISTS idx_job_created
    ON scan_jobs (created_at DESC);

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

CREATE TABLE IF NOT EXISTS notification_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    VARCHAR(255) NOT NULL,
    event_id   UUID REFERENCES extracted_events (id) ON DELETE SET NULL,
    channel    VARCHAR(50) NOT NULL,
    status     VARCHAR(20) DEFAULT 'pending',
    content    JSONB,
    sent_at    TIMESTAMPTZ,
    error_msg  TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_user
    ON notification_logs (user_id);

CREATE INDEX IF NOT EXISTS idx_notif_status
    ON notification_logs (status);

CREATE TABLE IF NOT EXISTS in_app_notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    VARCHAR(255) NOT NULL,
    title      VARCHAR(255) NOT NULL,
    content    TEXT,
    event_id   UUID REFERENCES extracted_events (id) ON DELETE SET NULL,
    severity   VARCHAR(20),
    action_url TEXT,
    is_read    BOOLEAN DEFAULT FALSE,
    read_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inapp_user
    ON in_app_notifications (user_id, is_read);

CREATE INDEX IF NOT EXISTS idx_inapp_created
    ON in_app_notifications (created_at DESC);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE in_app_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_user_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_source_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for scan source state" ON scan_source_state;
CREATE POLICY "Allow all for scan source state"
    ON scan_source_state FOR ALL USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_holdings_updated_at ON user_holdings;
CREATE TRIGGER update_user_holdings_updated_at
    BEFORE UPDATE ON user_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scan_source_state_updated_at ON scan_source_state;
CREATE TRIGGER update_scan_source_state_updated_at
    BEFORE UPDATE ON scan_source_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ---------------------------------------------------------------------------
-- 004_align_runtime_schema.sql
-- Safe to run on fresh databases and existing ones.
-- ---------------------------------------------------------------------------

ALTER TABLE user_holdings
    ADD COLUMN IF NOT EXISTS company VARCHAR(255);

UPDATE user_holdings
SET company = COALESCE(company, company_name)
WHERE company IS NULL;

CREATE INDEX IF NOT EXISTS idx_holdings_company
    ON user_holdings (company);

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS interested_categories TEXT[] DEFAULT ARRAY['E', 'S', 'G'];

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT ARRAY[]::TEXT[];

UPDATE user_preferences
SET interested_categories = ARRAY['E', 'S', 'G']
WHERE interested_categories IS NULL;

UPDATE user_preferences
SET keywords = ARRAY[]::TEXT[]
WHERE keywords IS NULL;

ALTER TABLE esg_events
    ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE esg_events
    ADD COLUMN IF NOT EXISTS raw_content TEXT;

ALTER TABLE esg_events
    ADD COLUMN IF NOT EXISTS detected_at TIMESTAMPTZ;

UPDATE esg_events
SET description = COALESCE(description, content)
WHERE description IS NULL;

UPDATE esg_events
SET raw_content = COALESCE(raw_content, content, description)
WHERE raw_content IS NULL;

UPDATE esg_events
SET detected_at = COALESCE(detected_at, scanned_at, created_at)
WHERE detected_at IS NULL;

ALTER TABLE extracted_events
    ADD COLUMN IF NOT EXISTS original_event_id UUID;

ALTER TABLE extracted_events
    ADD COLUMN IF NOT EXISTS impact_area VARCHAR(20);

ALTER TABLE extracted_events
    ADD COLUMN IF NOT EXISTS severity VARCHAR(20);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_name = 'extracted_events'
          AND constraint_name = 'extracted_events_original_event_id_fkey'
    ) THEN
        ALTER TABLE extracted_events
            ADD CONSTRAINT extracted_events_original_event_id_fkey
            FOREIGN KEY (original_event_id) REFERENCES esg_events (id) ON DELETE SET NULL;
    END IF;
END $$;

UPDATE extracted_events
SET original_event_id = COALESCE(original_event_id, raw_event_id)
WHERE original_event_id IS NULL;

UPDATE extracted_events
SET severity = COALESCE(severity, risk_level, 'low')
WHERE severity IS NULL;

UPDATE extracted_events
SET impact_area = COALESCE(
    impact_area,
    CASE
        WHEN affected_areas IS NULL OR array_length(affected_areas, 1) IS NULL THEN 'E'
        WHEN 'governance' = ANY(affected_areas) THEN 'G'
        WHEN 'social' = ANY(affected_areas) THEN 'S'
        ELSE 'E'
    END
)
WHERE impact_area IS NULL;

CREATE INDEX IF NOT EXISTS idx_extracted_original_event
    ON extracted_events (original_event_id);

CREATE INDEX IF NOT EXISTS idx_extracted_severity
    ON extracted_events (severity);

ALTER TABLE risk_scores
    ADD COLUMN IF NOT EXISTS recommendation TEXT;

UPDATE risk_scores
SET recommendation = COALESCE(
    recommendation,
    CASE
        WHEN recommendations IS NOT NULL AND array_length(recommendations, 1) > 0
        THEN recommendations[1]
        ELSE NULL
    END
)
WHERE recommendation IS NULL;

ALTER TABLE in_app_notifications
    ADD COLUMN IF NOT EXISTS severity VARCHAR(20);

ALTER TABLE in_app_notifications
    ADD COLUMN IF NOT EXISTS action_url TEXT;

UPDATE esg_events
SET event_type = LOWER(event_type)
WHERE event_type IS NOT NULL
  AND event_type <> LOWER(event_type);

-- ---------------------------------------------------------------------------
-- 007_add_auth_runtime_tables.sql
-- ---------------------------------------------------------------------------

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_hash TEXT;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);

UPDATE users
SET user_id = COALESCE(user_id, id::text)
WHERE user_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_id_unique
    ON users (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
    ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_email
    ON password_reset_tokens (email);

CREATE TABLE IF NOT EXISTS auth_audit (
    audit_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    email TEXT,
    user_id TEXT,
    success INTEGER NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_audit_event_created
    ON auth_audit (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_audit_email_created
    ON auth_audit (email, created_at DESC);

CREATE TABLE IF NOT EXISTS mailbox_delivery_logs (
    log_id TEXT PRIMARY KEY,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mailbox_delivery_logs_recipient_created
    ON mailbox_delivery_logs (recipient, created_at DESC);

CREATE TABLE IF NOT EXISTS ui_audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    target TEXT,
    before_json TEXT,
    after_json TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ui_audit_events_type_created
    ON ui_audit_events (event_type, created_at DESC);

ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE mailbox_delivery_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ui_audit_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for auth users" ON users;
CREATE POLICY "Allow all for auth users"
    ON users FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for password reset tokens" ON password_reset_tokens;
CREATE POLICY "Allow all for password reset tokens"
    ON password_reset_tokens FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for auth audit" ON auth_audit;
CREATE POLICY "Allow all for auth audit"
    ON auth_audit FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for mailbox delivery logs" ON mailbox_delivery_logs;
CREATE POLICY "Allow all for mailbox delivery logs"
    ON mailbox_delivery_logs FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all for ui audit events" ON ui_audit_events;
CREATE POLICY "Allow all for ui audit events"
    ON ui_audit_events FOR ALL USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS update_auth_users_updated_at ON users;
CREATE TRIGGER update_auth_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
