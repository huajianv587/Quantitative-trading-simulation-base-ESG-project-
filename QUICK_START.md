# ESG Agentic RAG Copilot - 快速开始指南

**版本**: 1.0.0 | **日期**: 2026-03-29 | **状态**: ✅ 生产就绪

---

## 🚀 5分钟快速启动

### 1️⃣ 复制配置文件

```bash
cp .env.example .env
```

### 2️⃣ 填入必需的API Key（最少需要这些）

编辑 `.env` 文件，填入以下内容：

```bash
# ════ 必需：LLM ════
ANTHROPIC_API_KEY=sk-ant-your-key-here

# ════ 必需：数据库 ════
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=your-api-key-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# ════ 推荐：财务数据 ════
ALPHA_VANTAGE_API_KEY=your-key-here

# ════ 推荐：新闻 ════
NEWSAPI_KEY=your-key-here
```

### 3️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

### 4️⃣ 运行数据库迁移

```bash
# 在Supabase SQL编辑器中执行：
# 1. migrations/001_initial_schema.sql
# 2. migrations/002_scheduler_tables.sql
# 3. migrations/003_add_esg_report_tables.sql
```

### 5️⃣ 启动应用

```bash
cd gateway
python main_enhanced.py
```

✅ **完成！** 应用运行在 `http://localhost:8000`

---

## 🔗 最常用的API调用

### 查询ESG评分

```bash
curl -X POST http://localhost:8000/agent/esg-score \
  -H "Content-Type: application/json" \
  -d '{"company": "Tesla", "include_visualization": true}'
```

### 生成周报告

```bash
curl -X POST http://localhost:8000/admin/reports/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "weekly",
    "companies": ["Tesla", "Apple"],
    "async": true
  }'
```

### 创建推送规则

```bash
curl -X POST http://localhost:8000/admin/push-rules \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "低分预警",
    "condition": "esg_score < 40",
    "target_users": "all",
    "push_channels": ["email", "in_app"],
    "priority": 8,
    "template_id": "template_low_esg_warning"
  }'
```

### 订阅报告

```bash
curl -X POST http://localhost:8000/user/reports/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "report_types": ["weekly", "monthly"],
    "companies": ["Tesla", "Apple"],
    "push_channels": ["email", "in_app"],
    "frequency": "daily"
  }'
```

---

## 📋 API Key 获取速查表

| 服务 | 获取地址 | 时间 | 成本 |
|-----|--------|------|------|
| **Anthropic** | https://console.anthropic.com | 2分钟 | 付费 |
| **Supabase** | https://app.supabase.com | 1分钟 | 免费+付费 |
| **Alpha Vantage** | https://www.alphavantage.co/ | 5分钟 | 免费+付费 |
| **NewsAPI** | https://newsapi.org/ | 2分钟 | 免费+付费 |
| **Finnhub** | https://finnhub.io/ | 3分钟 | 免费+付费 |

---

## 🧪 验证安装

```bash
# 检查健康状态
curl http://localhost:8000/health

# 应该返回：
# {
#   "status": "ok",
#   "modules": {
#     "rag": true,
#     "esg_scorer": true,
#     "report_scheduler": true
#   }
# }
```

---

## 📊 系统架构一览

```
用户查询
    ↓
┌─────────────────────────────────────┐
│  被动分析（用户主动提问）          │
├─────────────────────────────────────┤
│ /agent/analyze        → Agent工作流  │
│ /agent/esg-score      → 结构化评分   │
│ /query                → RAG问答      │
└─────────────────────────────────────┘
    ↓↑
┌─────────────────────────────────────┐
│  主动报告系统（定时自动生成）       │
├─────────────────────────────────────┤
│ /admin/reports/generate → 生成报告   │
│ /admin/reports/{id}     → 查询报告   │
│ /admin/push-rules       → 管理规则   │
│ /user/reports/subscribe → 用户订阅   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  智能推送系统（基于规则）            │
├─────────────────────────────────────┤
│ Email  │  In-App  │  Webhook  │ SMS  │
└─────────────────────────────────────┘
```

---

## ⚙️ 关键配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ENVIRONMENT` | 运行环境 | `development` |
| `SERVER_PORT` | 服务端口 | `8000` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `DAILY_REPORT_TIME` | 日报时间 | `06:00` |
| `WEEKLY_REPORT_TIME` | 周报时间 | `08:00` |
| `MONTHLY_REPORT_TIME` | 月报时间 | `09:00` |
| `CACHE_TTL` | 缓存过期时间(秒) | `3600` |

---

## 🐛 常见问题快速解决

**问题**: API Key不生效
```bash
# 解决: 重启应用，确保.env被加载
python main_enhanced.py
```

**问题**: 数据库连接失败
```bash
# 解决: 验证Supabase配置
python -c "from gateway.db.supabase_client import supabase_client; print('✓')"
```

**问题**: 报告生成超时
```bash
# 解决: 使用异步模式
# 在请求中设置 "async": true
```

---

## 📚 更多资源

| 文档 | 说明 |
|-----|------|
| [API_ENDPOINTS.md](./API_ENDPOINTS.md) | 完整API文档 |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | 详细部署指南 |
| [ENHANCEMENT_PLAN.md](./ENHANCEMENT_PLAN.md) | 系统增强方案 |
| [SCHEDULER_README.md](./SCHEDULER_README.md) | 调度器使用指南 |

---

## 🎯 下一步

1. ✅ 配置.env文件
2. ✅ 运行数据库迁移
3. ✅ 启动应用服务
4. ✅ 测试基础API
5. ✅ 创建推送规则
6. ✅ 配置定时报告
7. ✅ 集成前端应用

---

**现在您已准备好使用ESG Agentic RAG Copilot！** 🎉

需要帮助？查看 [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

