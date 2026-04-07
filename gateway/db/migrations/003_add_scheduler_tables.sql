-- Migration: 003_add_scheduler_tables.sql
-- Description: 添加调度器模块所需的数据库表
-- Date: 2026-03-30
--
-- 用途说明：
-- 这组表支持 ESG 事件的主动扫描、分析和推送功能。
-- 核心流程：扫描新闻 → 提取事件 → 风险评分 → 匹配用户 → 发送通知
--
-- 数据流向图：
-- [外部数据源] → esg_events → extracted_events → risk_scores
--                                    ↓
--                         event_user_matches → notification_logs / in_app_notifications
--                                    ↑
--                         user_preferences (匹配依据)

-- ────────────────────────────────────────────────────────────────────────────
-- 1. 用户表 (users)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储系统用户的基本信息
-- 使用场景：用户注册、权限管理、推送目标筛选

CREATE TABLE IF NOT EXISTS users (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),  -- 数据库内部主键
    user_id    VARCHAR(255) UNIQUE NOT NULL,  -- 业务用户ID（可能来自外部认证系统）
    email      VARCHAR(255),                  -- 邮箱，用于邮件推送
    name       VARCHAR(255),                  -- 用户显示名称
    role       VARCHAR(50)  DEFAULT 'user',   -- 角色：user普通用户, analyst分析师, admin管理员
    created_at TIMESTAMPTZ  DEFAULT NOW(),
    updated_at TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 用户持仓表 (user_holdings)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：记录用户持有的股票/公司
-- 使用场景：当持仓公司发生ESG事件时，优先通知持仓用户

CREATE TABLE IF NOT EXISTS user_holdings (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      VARCHAR(255) NOT NULL,       -- 持仓用户
    company      VARCHAR(255),                -- 运行时代码使用的公司字段
    company_name VARCHAR(255) NOT NULL,       -- 持仓公司名称
    ticker       VARCHAR(20),                 -- 股票代码，如"AAPL"
    shares       DECIMAL(18,4),               -- 持仓数量（股）
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (user_id, company_name)            -- 同一用户对同一公司只有一条记录
);

CREATE INDEX IF NOT EXISTS idx_holdings_user ON user_holdings (user_id);

-- ────────────────────────────────────────────────────────────────────────────
-- 3. 用户偏好表 (user_preferences)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储用户的关注偏好，用于事件匹配
-- 使用场景：根据用户偏好筛选相关事件进行推送

CREATE TABLE IF NOT EXISTS user_preferences (
    id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               VARCHAR(255) UNIQUE NOT NULL,
    watched_companies     TEXT[],      -- 关注的公司列表：["Apple", "Tesla"]
    interested_companies  TEXT[],      -- 感兴趣的公司（用于报告生成）
    interested_categories TEXT[]       DEFAULT ARRAY['E', 'S', 'G'],  -- 关注的 ESG 维度
    watched_industries    TEXT[],      -- 关注的行业：["Technology", "Energy"]
    risk_threshold        VARCHAR(20)  DEFAULT 'medium',  -- 风险阈值：low/medium/high/critical
    keywords              TEXT[]       DEFAULT ARRAY[]::TEXT[],       -- 关键词过滤
    notification_channels TEXT[]       DEFAULT ARRAY['in_app'],  -- 通知渠道偏好
    created_at            TIMESTAMPTZ  DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prefs_user ON user_preferences (user_id);

-- ────────────────────────────────────────────────────────────────────────────
-- 4. ESG 事件表 (esg_events) - 扫描器原始事件
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储从外部数据源扫描到的原始ESG相关信息
-- 使用场景：Scanner模块定期扫描新闻API，将原始数据存入此表
-- 这是整个事件处理流程的起点

CREATE TABLE IF NOT EXISTS esg_events (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    source      VARCHAR(100) NOT NULL,   -- 数据来源：newsapi/alphavantage/reuters
    source_url  TEXT,                    -- 原文链接
    title       VARCHAR(500),            -- 新闻标题
    description TEXT,                    -- 运行时代码使用的摘要字段
    content     TEXT,                    -- 新闻内容/摘要
    company     VARCHAR(255),            -- 相关公司（初步识别）
    event_type  VARCHAR(50),             -- 事件类型（初步分类）
    raw_content TEXT,                    -- 运行时代码使用的原始内容
    raw_data    JSONB,                   -- 原始API响应，保留完整数据
    detected_at TIMESTAMPTZ,             -- 运行时代码使用的检测时间
    scanned_at  TIMESTAMPTZ  DEFAULT NOW(),  -- 扫描时间
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_company ON esg_events (company);
CREATE INDEX IF NOT EXISTS idx_events_type ON esg_events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_scanned ON esg_events (scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_detected ON esg_events (detected_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. 提取事件表 (extracted_events) - LLM 结构化后的事件
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储经过LLM分析提取的结构化事件信息
-- 使用场景：EventExtractor模块用LLM分析原始事件，提取关键信息
-- 这是事件处理流程的第二步

CREATE TABLE IF NOT EXISTS extracted_events (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    original_event_id UUID       REFERENCES esg_events (id) ON DELETE SET NULL,  -- 运行时代码使用的外键名
    raw_event_id    UUID         REFERENCES esg_events (id) ON DELETE SET NULL,  -- 关联原始事件
    title           VARCHAR(500) NOT NULL,   -- LLM提取的事件标题
    description     TEXT,                    -- LLM生成的事件描述
    company         VARCHAR(255),            -- 确认的相关公司
    event_type      VARCHAR(50),             -- 事件类型：emission_reduction/safety_incident/governance_change等
    impact_area     VARCHAR(20),             -- 运行时代码使用的影响维度
    severity        VARCHAR(20),             -- 运行时代码使用的严重级别
    risk_level      VARCHAR(20),             -- 初步风险等级：low/medium/high/critical
    key_metrics     JSONB,                   -- 关键指标：{carbon_reduction: "15%", affected_employees: 500}
    affected_areas  TEXT[],                  -- 影响领域：["environmental", "social"]
    extracted_at    TIMESTAMPTZ  DEFAULT NOW(),
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extracted_company ON extracted_events (company);
CREATE INDEX IF NOT EXISTS idx_extracted_risk ON extracted_events (risk_level);
CREATE INDEX IF NOT EXISTS idx_extracted_created ON extracted_events (created_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 6. 风险评分表 (risk_scores)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储LLM对事件的深度风险评估结果
-- 使用场景：RiskScorer模块对提取的事件进行风险评分
-- 这是事件处理流程的第三步

CREATE TABLE IF NOT EXISTS risk_scores (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID         REFERENCES extracted_events (id) ON DELETE CASCADE,  -- 关联提取事件
    risk_level          VARCHAR(20)  NOT NULL,   -- 风险等级：low/medium/high/critical
    score               INT          CHECK (score >= 0 AND score <= 100),  -- 风险分数0-100
    reasoning           TEXT,                    -- LLM给出的评分理由
    affected_dimensions JSONB,                   -- 各维度影响：{environmental: 80, social: 60, governance: 40}
    recommendation      TEXT,                    -- 运行时代码使用的单条建议
    recommendations     TEXT[],                  -- LLM建议的应对措施
    scored_at           TIMESTAMPTZ  DEFAULT NOW(),
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_event ON risk_scores (event_id);
CREATE INDEX IF NOT EXISTS idx_risk_level ON risk_scores (risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_score ON risk_scores (score DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 7. 事件-用户匹配表 (event_user_matches)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：记录事件与用户的匹配关系
-- 使用场景：Matcher模块根据用户偏好匹配相关事件
-- 这是事件处理流程的第四步

CREATE TABLE IF NOT EXISTS event_user_matches (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id      UUID         REFERENCES extracted_events (id) ON DELETE CASCADE,
    user_id       VARCHAR(255) NOT NULL,
    match_reason  TEXT,        -- 匹配原因："持仓公司"/"关注行业"/"风险阈值触发"
    relevance     DECIMAL(5,2),-- 相关度评分0-100
    matched_at    TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (event_id, user_id) -- 同一事件对同一用户只匹配一次
);

CREATE INDEX IF NOT EXISTS idx_match_user ON event_user_matches (user_id);
CREATE INDEX IF NOT EXISTS idx_match_event ON event_user_matches (event_id);

-- ────────────────────────────────────────────────────────────────────────────
-- 8. 扫描任务表 (scan_jobs)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：记录扫描任务的执行状态
-- 使用场景：监控扫描任务运行情况，排查问题

CREATE TABLE IF NOT EXISTS scan_jobs (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type     VARCHAR(50)  NOT NULL,   -- 任务类型：news_scan/report_scan/social_scan
    status       VARCHAR(20)  DEFAULT 'pending',  -- 状态：pending/running/completed/failed
    started_at   TIMESTAMPTZ,             -- 开始时间
    completed_at TIMESTAMPTZ,             -- 完成时间
    events_found INT          DEFAULT 0,  -- 发现的事件数量
    error_msg    TEXT,                    -- 错误信息（如果失败）
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_status ON scan_jobs (status);
CREATE INDEX IF NOT EXISTS idx_job_created ON scan_jobs (created_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 9. 通知日志表 (notification_logs)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：记录所有渠道的通知发送记录
-- 使用场景：追踪通知发送状态，排查发送失败问题

CREATE TABLE IF NOT EXISTS notification_logs (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      VARCHAR(255) NOT NULL,
    event_id     UUID         REFERENCES extracted_events (id) ON DELETE SET NULL,
    channel      VARCHAR(50)  NOT NULL,   -- 发送渠道：email/webhook/sms
    status       VARCHAR(20)  DEFAULT 'pending',  -- 状态：pending/sent/failed
    content      JSONB,                   -- 发送内容
    sent_at      TIMESTAMPTZ,             -- 发送时间
    error_msg    TEXT,                    -- 错误信息
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_user ON notification_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_notif_status ON notification_logs (status);

-- ────────────────────────────────────────────────────────────────────────────
-- 10. 应用内通知表 (in_app_notifications)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储应用内通知（显示在前端通知中心）
-- 使用场景：用户登录后查看未读通知

CREATE TABLE IF NOT EXISTS in_app_notifications (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    VARCHAR(255) NOT NULL,
    title      VARCHAR(255) NOT NULL,    -- 通知标题
    content    TEXT,                     -- 通知内容
    event_id   UUID         REFERENCES extracted_events (id) ON DELETE SET NULL,  -- 关联事件（可点击查看详情）
    severity   VARCHAR(20),              -- 运行时代码使用的严重级别
    action_url TEXT,                     -- 前端跳转链接
    is_read    BOOLEAN      DEFAULT FALSE,  -- 是否已读
    read_at    TIMESTAMPTZ,              -- 阅读时间
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inapp_user ON in_app_notifications (user_id, is_read);  -- 查询用户未读通知
CREATE INDEX IF NOT EXISTS idx_inapp_created ON in_app_notifications (created_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 11. 启用 RLS（行级安全）
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE users                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_holdings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences       ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE in_app_notifications   ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_user_matches     ENABLE ROW LEVEL SECURITY;

-- ────────────────────────────────────────────────────────────────────────────
-- 12. 触发器：自动更新 updated_at
-- ────────────────────────────────────────────────────────────────────────────
-- 注意：update_updated_at_column() 函数在 002 中已定义

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_holdings_updated_at
    BEFORE UPDATE ON user_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
