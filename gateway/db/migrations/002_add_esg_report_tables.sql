-- Migration: 002_add_esg_report_tables.sql
-- Description: 添加ESG报告系统相关的数据库表
-- Date: 2026-03-29
--
-- 用途说明：
-- 这组表支持 ESG 报告的生成、存储和智能推送功能。
-- 核心流程：生成报告 → 匹配规则 → 推送给目标用户 → 收集反馈
-- 
-- 表关系图：
-- esg_reports ──┬── report_push_history ── push_feedback
--               │
-- push_rules ───┘
-- user_report_subscriptions (独立，用户主动订阅)
-- company_data_snapshot (独立，企业数据快照)

-- ────────────────────────────────────────────────────────────────────────────
-- 1. ESG 报告表 (esg_reports)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储系统生成的 ESG 分析报告
-- 使用场景：定时任务生成日报/周报/月报，用户在报告页面查看

CREATE TABLE IF NOT EXISTS esg_reports (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),  -- 报告唯一ID
    report_type  VARCHAR(20)  NOT NULL,   -- 报告类型："daily"日报, "weekly"周报, "monthly"月报
    title        VARCHAR(255) NOT NULL,   -- 报告标题，如"2026年3月ESG周报"
    period_start TIMESTAMP    NOT NULL,   -- 报告覆盖的起始时间
    period_end   TIMESTAMP    NOT NULL,   -- 报告覆盖的结束时间
    data         JSONB        NOT NULL,   -- 报告内容（JSON格式），包含评分、分析、图表数据等
    generated_at TIMESTAMP    NOT NULL DEFAULT NOW(),  -- 报告生成时间
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),  -- 记录创建时间

    UNIQUE (report_type, period_start, period_end)  -- 同类型同时段只能有一份报告
);

CREATE INDEX IF NOT EXISTS idx_report_type_date ON esg_reports (report_type, generated_at DESC);  -- 按类型+时间查询
CREATE INDEX IF NOT EXISTS idx_period           ON esg_reports (period_start, period_end);        -- 按时间段查询

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 企业数据快照表 (company_data_snapshot)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：定期保存企业的 ESG 数据快照，用于历史对比和趋势分析
-- 使用场景：每日同步企业数据，生成报告时读取快照

CREATE TABLE IF NOT EXISTS company_data_snapshot (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name      VARCHAR(255) NOT NULL,   -- 公司名称，如"Apple Inc."
    ticker            VARCHAR(10),             -- 股票代码，如"AAPL"
    industry          VARCHAR(100),            -- 所属行业，如"Technology"
    esg_score_report  JSONB,       -- ESG评分详情：{overall: 75, e: 80, s: 70, g: 75}
    financial_metrics JSONB,       -- 财务指标：{revenue: 1000000, market_cap: 5000000}
    external_ratings  JSONB,       -- 外部评级：{msci: "AA", sustainalytics: 25}
    snapshot_date     DATE         NOT NULL,   -- 快照日期
    last_updated      TIMESTAMP    NOT NULL DEFAULT NOW(),

    UNIQUE (company_name, snapshot_date)  -- 每家公司每天只有一个快照
);

CREATE INDEX IF NOT EXISTS idx_company_date   ON company_data_snapshot (company_name, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_snapshot_date  ON company_data_snapshot (snapshot_date);

-- ────────────────────────────────────────────────────────────────────────────
-- 3. 报告推送历史表 (report_push_history)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：记录每份报告推送给了哪些用户，以及用户的阅读行为
-- 使用场景：追踪推送效果、避免重复推送、分析用户参与度

CREATE TABLE IF NOT EXISTS report_push_history (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id     UUID         NOT NULL REFERENCES esg_reports (id) ON DELETE CASCADE,  -- 关联的报告
    user_id       VARCHAR(255) NOT NULL,   -- 接收用户ID
    push_channels TEXT[]       NOT NULL,   -- 推送渠道：["in_app", "email", "webhook"]
    push_status   VARCHAR(20)  NOT NULL DEFAULT 'pending',  -- 推送状态：pending/sent/failed
    delivered_at  TIMESTAMP,               -- 实际送达时间
    read_at       TIMESTAMP,               -- 用户阅读时间（打开报告时更新）
    click_through BOOLEAN      DEFAULT FALSE,  -- 用户是否点击了报告中的链接
    feedback_score INT         CHECK (feedback_score >= 1 AND feedback_score <= 5),  -- 用户评分1-5星
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),

    UNIQUE (report_id, user_id)  -- 同一报告对同一用户只推送一次
);

CREATE INDEX IF NOT EXISTS idx_user_push    ON report_push_history (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_push  ON report_push_history (report_id, push_status);
CREATE INDEX IF NOT EXISTS idx_push_status  ON report_push_history (push_status);

-- ────────────────────────────────────────────────────────────────────────────
-- 4. 推送规则表 (push_rules)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：定义智能推送规则，满足条件时自动触发推送
-- 使用场景：管理员配置规则，如"ESG评分低于40时通知持仓用户"

CREATE TABLE IF NOT EXISTS push_rules (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name     VARCHAR(255) NOT NULL UNIQUE,  -- 规则名称，如"warn_low_esg"
    condition     TEXT         NOT NULL,   -- 触发条件（Python表达式），如"esg_score < 40 and change < -5"
    target_users  VARCHAR(50)  NOT NULL,   -- 目标用户群："all"全部, "holders"持仓者, "followers"关注者, "analysts"分析师
    push_channels TEXT[]       NOT NULL,   -- 推送渠道：["email", "in_app", "webhook"]
    priority      INT          NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),  -- 优先级1-10，越高越优先
    template_id   VARCHAR(255) NOT NULL,   -- 消息模板ID，用于生成推送内容
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,   -- 是否启用
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enabled_priority ON push_rules (enabled, priority DESC);
CREATE INDEX IF NOT EXISTS idx_target_users     ON push_rules (target_users);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. 用户报告订阅表 (user_report_subscriptions)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：用户主动订阅特定类型的报告
-- 使用场景：用户在设置页面选择要接收的报告类型和关注的公司

CREATE TABLE IF NOT EXISTS user_report_subscriptions (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          VARCHAR(255) NOT NULL,   -- 订阅用户ID
    report_types     TEXT[]       NOT NULL,   -- 订阅的报告类型：["daily", "weekly", "monthly"]
    companies        TEXT[]       NOT NULL,   -- 关注的公司列表：["Apple", "Microsoft"]
    alert_threshold  JSONB        NOT NULL,   -- 告警阈值：{"esg_score": 40, "change": -5}
    push_channels    TEXT[]       NOT NULL,   -- 接收渠道：["email", "in_app"]
    frequency        VARCHAR(50)  NOT NULL DEFAULT 'daily',  -- 推送频率：immediate/daily/weekly
    subscribed_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions ON user_report_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_frequency          ON user_report_subscriptions (frequency);

-- ────────────────────────────────────────────────────────────────────────────
-- 6. 推送反馈表 (push_feedback)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：收集用户对推送内容的详细反馈
-- 使用场景：优化推送策略、改进报告质量

CREATE TABLE IF NOT EXISTS push_feedback (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    push_history_id  UUID         NOT NULL REFERENCES report_push_history (id) ON DELETE CASCADE,  -- 关联的推送记录
    user_id          VARCHAR(255) NOT NULL,
    rating           INT          CHECK (rating >= 1 AND rating <= 5),  -- 评分1-5星
    feedback_text    TEXT,        -- 文字反馈
    action_taken     VARCHAR(50), -- 用户行为："read"已读, "deleted"删除, "shared"分享, "forwarded"转发
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_feedback    ON push_feedback (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_rating  ON push_feedback (rating);

-- ────────────────────────────────────────────────────────────────────────────
-- 7. 视图：报告推送统计 (report_push_statistics)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：聚合每份报告的推送效果指标
-- 使用场景：管理后台查看报告的触达率、阅读率、点击率

CREATE OR REPLACE VIEW report_push_statistics AS
SELECT
    rph.report_id,
    COUNT(*)                                                                              AS total_pushed,      -- 总推送数
    COUNT(CASE WHEN rph.delivered_at IS NOT NULL THEN 1 END)                             AS delivered_count,   -- 送达数
    COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END)                                  AS read_count,        -- 阅读数
    COUNT(CASE WHEN rph.click_through THEN 1 END)                                        AS click_count,       -- 点击数
    ROUND(100.0 * COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END)
          / NULLIF(COUNT(*), 0), 2)                                                      AS read_rate,         -- 阅读率%
    ROUND(100.0 * COUNT(CASE WHEN rph.click_through THEN 1 END)
          / NULLIF(COUNT(*), 0), 2)                                                      AS ctr,               -- 点击率%
    AVG(CASE WHEN rph.feedback_score IS NOT NULL THEN rph.feedback_score ELSE 0 END)     AS avg_feedback_score -- 平均评分
FROM report_push_history rph
GROUP BY rph.report_id;

-- 视图：用户推送活跃度（最近 30 天）
CREATE OR REPLACE VIEW user_push_activity AS
SELECT
    rph.user_id,
    COUNT(*)                                                                              AS total_pushed,
    COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END)                                  AS read_count,
    COUNT(CASE WHEN rph.click_through THEN 1 END)                                        AS click_count,
    MAX(rph.delivered_at)                                                                 AS last_push_date,
    ROUND(100.0 * COUNT(CASE WHEN rph.read_at IS NOT NULL THEN 1 END)
          / NULLIF(COUNT(*), 0), 2)                                                      AS engagement_rate
FROM report_push_history rph
WHERE rph.created_at >= NOW() - INTERVAL '30 days'
GROUP BY rph.user_id;

-- ────────────────────────────────────────────────────────────────────────────
-- 8. 行级安全策略（RLS）
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：限制用户只能访问自己的数据（Supabase 特性）
-- 注意：当前配置为允许所有访问，生产环境应根据需求调整

ALTER TABLE esg_reports                ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_data_snapshot      ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_push_history        ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_rules                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_report_subscriptions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_feedback              ENABLE ROW LEVEL SECURITY;

-- 简化的 RLS 策略：允许所有访问（开发阶段）
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

-- ────────────────────────────────────────────────────────────────────────────
-- 9. 触发器：自动更新 updated_at
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：每次 UPDATE 时自动刷新 updated_at 字段

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_push_rules_updated_at ON push_rules;
CREATE TRIGGER update_push_rules_updated_at
    BEFORE UPDATE ON push_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_report_subscriptions_updated_at ON user_report_subscriptions;
CREATE TRIGGER update_user_report_subscriptions_updated_at
    BEFORE UPDATE ON user_report_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ────────────────────────────────────────────────────────────────────────────
-- 10. 初始推送规则示例
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：预置几条常用的推送规则

INSERT INTO push_rules (rule_name, condition, target_users, push_channels, priority, template_id, enabled)
VALUES
    ('warn_low_esg',        'low_performer_count > 0',  'holders',  ARRAY['email', 'in_app'], 8,  'template_low_esg_warning', true),  -- ESG低分预警
    ('highlight_excellence','high_performer_count > 0', 'all',      ARRAY['in_app'],          5,  'template_excellence',      true),  -- 优秀企业推荐
    ('critical_risk_alert', 'overall_score < 30',       'analysts', ARRAY['email', 'webhook'],10, 'template_critical_alert',  true)   -- 严重风险告警
ON CONFLICT (rule_name) DO NOTHING;
