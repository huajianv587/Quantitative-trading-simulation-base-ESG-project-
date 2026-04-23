-- Auth runtime schema required for Supabase-primary register/login/reset flows.
-- Safe to run on existing projects after 000/001/003.

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

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
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
