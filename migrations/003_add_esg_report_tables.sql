-- Migration: 003_add_esg_report_tables.sql
-- Description: 添加ESG报告系统相关的数据库表
-- Date: 2026-03-29

-- ────────────────────────────────────────────────────────────────────────────
-- 1. ESG 报告表
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS esg_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type VARCHAR(20) NOT NULL,  -- "daily", "weekly", "monthly"
    title VARCHAR(255) NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,

    -- 完整报告数据（JSON格式）
    data JSONB NOT NULL,

    -- 元数据
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 索引
    UNIQUE(report_type, period_start, period_end),
    INDEX idx_report_type_date (report_type, generated_at DESC),
    INDEX idx_period (period_start, period_end)
);

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 企业数据快照表（用于缓存数据）
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS company_data_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    ticker VARCHAR(10),
    industry VARCHAR(100),

    -- ESG评分报告（JSON）
    esg_score_report JSONB,

    -- 财务指标（JSON）
    financial_metrics JSONB,

    -- 外部ESG评分（JSON）
    external_ratings JSONB,

    -- 时间戳
    snapshot_date DATE NOT NULL,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 索引
    UNIQUE(company_name, snapshot_date),
    INDEX idx_company_date (company_name, snapshot_date DESC),
    INDEX idx_snapshot_date (snapshot_date)
);

-- ────────────────────────────────────────────────────────────────────────────
-- 3. 报告推送历史表
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS report_push_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES esg_reports(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,

    -- 推送状态
    push_channels TEXT[] NOT NULL,  -- ["in_app", "email", "webhook"]
    push_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- "sent", "failed", "pending"

    -- 送达和阅读时间
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    click_through BOOLEAN DEFAULT FALSE,

    -- 用户反馈
    feedback_score INT CHECK (feedback_score >= 1 AND feedback_score <= 5),

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 索引
    UNIQUE(report_id, user_id),
    INDEX idx_user_push (user_id, created_at DESC),
    INDEX idx_report_push (report_id, push_status),
    INDEX idx_push_status (push_status)
);

-- ────────────────────────────────────────────────────────────────────────────
-- 4. 推送规则表
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS push_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(255) NOT NULL UNIQUE,

    -- 规则条件和目标
    condition TEXT NOT NULL,  -- Python表达式，如 "esg_score < 40 and change < -5"
    target_users VARCHAR(50) NOT NULL,  -- "all", "holders", "followers", "analysts"
    push_channels TEXT[] NOT NULL,  -- ["in_app", "email", "webhook"]

    -- 优先级和模板
    priority INT NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    template_id VARCHAR(255) NOT NULL,

    -- 启用状态
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 索引
    INDEX idx_enabled_priority (enabled, priority DESC),
    INDEX idx_target_users (target_users)
);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. 用户报告订阅表
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_report_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,

    -- 订阅的报告类型和公司
    report_types TEXT[] NOT NULL,  -- ["daily", "weekly", "monthly"]
    companies TEXT[] NOT NULL,

    -- 告警阈值
    alert_threshold JSONB NOT NULL,  -- {"esg_score": 40, "change": -5}

    -- 推送渠道和频率
    push_channels TEXT[] NOT NULL,
    frequency VARCHAR(50) NOT NULL DEFAULT 'daily',  -- "immediate", "daily", "weekly"

    -- 时间戳
    subscribed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 索引
    INDEX idx_user_subscriptions (user_id),
    INDEX idx_frequency (frequency)
);

-- ────────────────────────────────────────────────────────────────────────────
-- 6. 推送反馈表（用于优化推送策略）
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS push_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    push_history_id UUID NOT NULL REFERENCES report_push_history(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,

    -- 反馈信息
    rating INT CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    action_taken VARCHAR(50),  -- "read", "deleted", "shared", "forwarded"

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- 索引
    INDEX idx_user_feedback (user_id, created_at DESC),
    INDEX idx_feedback_rating (rating)
);

-- ────────────────────────────────────────────────────────────────────────────
-- 7. 创建视图用于常见查询
-- ────────────────────────────────────────────────────────────────────────────

-- 报告推送统计视图
CREATE OR REPLACE VIEW report_push_statistics AS
SELECT
    rph.report_id,
    COUNT(*) as total_pushed,
    COUNT(CASE WHEN rph.delivered_at IS NOT NULL THEN 1 END) as delivered_count,
    COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) as read_count,
    COUNT(CASE WHEN rph.click_through THEN 1 END) as click_count,
    ROUND(100.0 * COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 2) as read_rate,
    ROUND(100.0 * COUNT(CASE WHEN rph.click_through THEN 1 END) / NULLIF(COUNT(*), 0), 2) as ctr,
    AVG(CASE WHEN rph.feedback_score IS NOT NULL THEN rph.feedback_score ELSE 0 END) as avg_feedback_score
FROM report_push_history rph
GROUP BY rph.report_id;

-- 用户推送活跃度视图
CREATE OR REPLACE VIEW user_push_activity AS
SELECT
    rph.user_id,
    COUNT(*) as total_pushed,
    COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) as read_count,
    COUNT(CASE WHEN rph.click_through THEN 1 END) as click_count,
    MAX(rph.delivered_at) as last_push_date,
    ROUND(100.0 * COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END) / NULLIF(COUNT(*), 0), 2) as engagement_rate
FROM report_push_history rph
WHERE rph.created_at >= NOW() - INTERVAL '30 days'
GROUP BY rph.user_id;

-- ────────────────────────────────────────────────────────────────────────────
-- 8. 设置行级安全策略（RLS）
-- ────────────────────────────────────────────────────────────────────────────

-- 启用RLS
ALTER TABLE esg_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_data_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_push_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_report_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_feedback ENABLE ROW LEVEL SECURITY;

-- 政策：允许管理员查看所有报告
CREATE POLICY "Admin can view all reports" ON esg_reports
    FOR SELECT
    USING (auth.jwt_get_claim('role') = 'admin');

-- 政策：用户只能看到发送给他们的推送历史
CREATE POLICY "Users can view own push history" ON report_push_history
    FOR SELECT
    USING (auth.uid()::text = user_id OR auth.jwt_get_claim('role') = 'admin');

-- 政策：用户只能管理自己的订阅
CREATE POLICY "Users can manage own subscriptions" ON user_report_subscriptions
    FOR ALL
    USING (auth.uid()::text = user_id OR auth.jwt_get_claim('role') = 'admin')
    WITH CHECK (auth.uid()::text = user_id OR auth.jwt_get_claim('role') = 'admin');

-- 政策：只有管理员可以管理推送规则
CREATE POLICY "Admins can manage push rules" ON push_rules
    FOR ALL
    USING (auth.jwt_get_claim('role') = 'admin')
    WITH CHECK (auth.jwt_get_claim('role') = 'admin');

-- ────────────────────────────────────────────────────────────────────────────
-- 9. 创建触发器用于自动更新时间戳
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_push_rules_updated_at BEFORE UPDATE ON push_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_report_subscriptions_updated_at BEFORE UPDATE ON user_report_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ────────────────────────────────────────────────────────────────────────────
-- 10. 创建初始推送规则示例
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO push_rules (rule_name, condition, target_users, push_channels, priority, template_id, enabled)
VALUES
    ('warn_low_esg', 'low_performer_count > 0', 'holders', ARRAY['email', 'in_app'], 8, 'template_low_esg_warning', true),
    ('highlight_excellence', 'high_performer_count > 0', 'all', ARRAY['in_app'], 5, 'template_excellence', true),
    ('critical_risk_alert', 'overall_score < 30', 'analysts', ARRAY['email', 'webhook'], 10, 'template_critical_alert', true)
ON CONFLICT (rule_name) DO NOTHING;

-- ────────────────────────────────────────────────────────────────────────────
-- 完成标记
-- ────────────────────────────────────────────────────────────────────────────
-- Migration 完成：已创建ESG报告系统的所有必需表和视图
-- 请在Supabase仪表板中执行此SQL脚本
