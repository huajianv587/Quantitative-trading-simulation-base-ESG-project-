-- Migration: 001_init_sessions.sql
-- Description: 初始化会话管理和聊天记录表
-- Date: 2026-03-30
-- 
-- 用途说明：
-- 这是整个系统的基础表，用于支持多轮对话功能。
-- 用户每次开始新对话时创建一个 session，所有消息都关联到这个 session。
-- 这样可以实现：1) 对话历史回溯 2) 上下文记忆 3) 多会话管理

-- ────────────────────────────────────────────────────────────────────────────
-- 1. 会话表 (sessions)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：记录每个对话会话的元信息
-- 使用场景：用户打开聊天页面时创建新会话，或恢复历史会话

CREATE TABLE IF NOT EXISTS sessions (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),  -- 数据库内部主键，自动生成
    session_id TEXT        UNIQUE NOT NULL,  -- 前端生成的会话ID（如 "session_abc123"），用于API调用
    user_id    TEXT,                         -- 关联用户ID，匿名用户为NULL，登录用户可追踪历史
    created_at TIMESTAMPTZ DEFAULT NOW()     -- 会话创建时间，用于排序和清理过期会话
);

-- 索引说明：
CREATE INDEX IF NOT EXISTS idx_sessions_user_id    ON sessions (user_id);        -- 加速"查询某用户所有会话"
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions (created_at DESC); -- 加速"按时间倒序列出会话"

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 聊天记录表 (chat_history)
-- ────────────────────────────────────────────────────────────────────────────
-- 作用：存储每条对话消息（用户问题 + AI回答）
-- 使用场景：
--   1. 加载历史对话显示在聊天界面
--   2. 构建 LLM 上下文（把历史消息拼接成 prompt）
--   3. 对话分析和质量评估

CREATE TABLE IF NOT EXISTS chat_history (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),  -- 消息唯一ID
    session_id TEXT        NOT NULL                                -- 关联的会话ID
                           REFERENCES sessions (session_id) ON DELETE CASCADE,  -- 删除会话时自动删除所有消息
    role       TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),  -- 消息发送方：user=用户提问，assistant=AI回答
    content    TEXT        NOT NULL,   -- 消息内容（支持 Markdown 格式）
    created_at TIMESTAMPTZ DEFAULT NOW()  -- 消息发送时间，用于排序
);

-- 索引说明：
CREATE INDEX IF NOT EXISTS idx_chat_session_created ON chat_history (session_id, created_at);  -- 加速"按时间顺序获取某会话的消息"
