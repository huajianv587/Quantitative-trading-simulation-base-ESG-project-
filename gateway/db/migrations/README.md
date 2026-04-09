# Database Migrations

所有 Supabase 表结构定义集中在此目录，按编号顺序执行。

## 执行方式

在 Supabase 控制台 → SQL Editor 中，按序粘贴并运行每个文件的内容。

| 文件 | 内容 |
|------|------|
| `000_supabase_bootstrap_all.sql` | 单文件整段初始化版，适合全新 Supabase 项目一次性执行 |
| `001_init_sessions.sql` | `sessions` 会话表、`chat_history` 聊天记录表 |
| `002_add_esg_report_tables.sql` | ESG 报告、企业快照、推送历史、推送规则、订阅、反馈表及相关视图/触发器 |
| `003_add_scheduler_tables.sql` | 用户、持仓、偏好、ESG事件、提取事件、风险评分、匹配、扫描任务、通知日志、应用内通知表 |

## 注意事项

- 所有文件均使用 `CREATE TABLE IF NOT EXISTS`，重复执行安全。
- `002` 依赖 `001` 已存在（无直接外键，但逻辑上先建基础表）。
- RLS 策略依赖 Supabase Auth（`auth.uid()`、`auth.jwt_get_claim()`），本地 PostgreSQL 不支持。
