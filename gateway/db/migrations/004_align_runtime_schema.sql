-- Migration: 004_align_runtime_schema.sql
-- Description: 对齐现有 Supabase 表结构与运行时代码字段
-- Date: 2026-03-30
--
-- 用途：
-- 1. 修复旧 schema 与当前 Python 代码之间的字段名漂移
-- 2. 尽量保留现有数据并做安全回填
-- 3. 让 dashboard / scanner / extractor / scorer / notifier / scheduler 使用同一套字段

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. user_holdings
-- 运行时代码读取 company，旧表只有 company_name
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE user_holdings
    ADD COLUMN IF NOT EXISTS company VARCHAR(255);

UPDATE user_holdings
SET company = COALESCE(company, company_name)
WHERE company IS NULL;

CREATE INDEX IF NOT EXISTS idx_holdings_company ON user_holdings (company);

-- ────────────────────────────────────────────────────────────────────────────
-- 2. user_preferences
-- 运行时代码使用 interested_categories / keywords
-- ────────────────────────────────────────────────────────────────────────────
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

-- ────────────────────────────────────────────────────────────────────────────
-- 3. esg_events
-- 运行时代码使用 description / raw_content / detected_at
-- 旧表常见字段为 content / raw_data / scanned_at
-- ────────────────────────────────────────────────────────────────────────────
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

CREATE INDEX IF NOT EXISTS idx_events_detected ON esg_events (detected_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 4. extracted_events
-- 运行时代码使用 original_event_id / impact_area / severity
-- 旧表常见字段为 raw_event_id / affected_areas / risk_level
-- ────────────────────────────────────────────────────────────────────────────
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

CREATE INDEX IF NOT EXISTS idx_extracted_original_event ON extracted_events (original_event_id);
CREATE INDEX IF NOT EXISTS idx_extracted_severity ON extracted_events (severity);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. risk_scores
-- 运行时代码写 recommendation，旧表为 recommendations[]
-- ────────────────────────────────────────────────────────────────────────────
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

-- ────────────────────────────────────────────────────────────────────────────
-- 6. in_app_notifications
-- 运行时代码写 severity / action_url
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE in_app_notifications
    ADD COLUMN IF NOT EXISTS severity VARCHAR(20);

ALTER TABLE in_app_notifications
    ADD COLUMN IF NOT EXISTS action_url TEXT;

-- ────────────────────────────────────────────────────────────────────────────
-- 7. 辅助修正：确保旧数据可被当前 dashboard 正常读取
-- ────────────────────────────────────────────────────────────────────────────
UPDATE esg_events
SET event_type = LOWER(event_type)
WHERE event_type IS NOT NULL
  AND event_type <> LOWER(event_type);

COMMIT;
