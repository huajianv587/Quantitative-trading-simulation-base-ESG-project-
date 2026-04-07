# ESG Agentic RAG Copilot - 完整部署指南

> 注意：这份文档包含较早阶段的历史内容，不应再作为当前交付的唯一依据。
> 当前请优先以 `README.md`、`deploy/README.md`、`docs/LOCAL_HYBRID_RUNBOOK*.md`
> 和 `docs/REMOTE_GPU_RUNBOOK.md` 为准。

**项目完成日期**: 2026-03-29
**版本**: 1.0.0
**状态**: ⚠️ 历史文档，需按当前代码与运行手册复核

---

## 📋 目录

1. [项目结构](#项目结构)
2. [必需的API Key](#必需的api-key)
3. [环境配置](#环境配置)
4. [数据库设置](#数据库设置)
5. [依赖安装](#依赖安装)
6. [项目启动](#项目启动)
7. [验证和测试](#验证和测试)
8. [常见问题](#常见问题)

---

## 🏗️ 项目结构

```
ESG-Agentic-RAG-Copilot/
├── gateway/
│   ├── agents/
│   │   ├── esg_scorer.py              # ✨ 新增：结构化ESG评分框架
│   │   ├── esg_visualizer.py          # ✨ 新增：可视化数据生成
│   │   ├── analyst_agent.py           # 现有：分析Agent
│   │   ├── retriever_agent.py         # 现有：检索Agent
│   │   ├── verifier_agent.py          # 现有：验证Agent
│   │   └── router_agent.py            # 现有：路由Agent
│   │
│   ├── scheduler/
│   │   ├── data_sources.py            # ✨ 新增：多源数据集成
│   │   ├── report_generator.py        # ✨ 新增：报告生成引擎
│   │   ├── report_scheduler.py        # ✨ 新增：定时调度和推送
│   │   ├── scanner.py                 # 现有：事件扫描
│   │   ├── event_extractor.py         # 现有：事件提取
│   │   ├── matcher.py                 # 现有：事件匹配
│   │   ├── risk_scorer.py             # 现有：风险评分
│   │   ├── notifier.py                # 现有：通知推送
│   │   └── orchestrator.py            # 现有：流程编排
│   │
│   ├── models/
│   │   └── schemas.py                 # 数据模型（已更新）
│   │
│   ├── main.py                        # 现有的API入口
│   └── main_enhanced.py               # ✨ 新增：增强的API入口（包含所有新端点）
│
├── migrations/
│   ├── 001_initial_schema.sql        # 现有：初始Schema
│   ├── 002_scheduler_tables.sql      # 现有：Scheduler表
│   └── 003_add_esg_report_tables.sql # ✨ 新增：报告系统表
│
├── .env.example                      # ✨ 新增：环境配置示例
├── API_ENDPOINTS.md                  # ✨ 新增：完整API文档
├── DEPLOYMENT_GUIDE.md               # ✨ 新增：部署指南（本文件）
├── ENHANCEMENT_PLAN.md               # ✨ 新增：增强方案文档
├── IMPLEMENTATION_SUMMARY.md         # 现有：实现总结
├── SCHEDULER_README.md               # 现有：调度器文档
└── requirements.txt                  # 依赖列表（需更新）
```

---

## 🔑 必需的API Key

### ✅ **必需的API**（核心功能）

| API服务 | 名称 | 获取地址 | 用途 |
|--------|------|--------|------|
| **Anthropic** | ANTHROPIC_API_KEY | https://console.anthropic.com/account/keys | Claude LLM模型 |
| **Supabase** | SUPABASE_URL<br/>SUPABASE_API_KEY<br/>SUPABASE_SERVICE_ROLE_KEY | https://app.supabase.com/projects | PostgreSQL数据库 |

### ⚠️ **强烈推荐**（提升数据质量）

| API服务 | 名称 | 获取地址 | 用途 |
|--------|------|--------|------|
| **Alpha Vantage** | ALPHA_VANTAGE_API_KEY | https://www.alphavantage.co/ | 财务数据、股价 |
| **NewsAPI** | NEWSAPI_KEY | https://newsapi.org/ | ESG相关新闻 |
| **Finnhub** | FINNHUB_API_KEY | https://finnhub.io/dashboard/api-tokens | 股票和企业数据 |

### 📊 **可选的API**（增强功能）

| API服务 | 名称 | 获取地址 | 用途 |
|--------|------|--------|------|
| **Hyfinnan** | HYFINNAN_API_KEY | https://www.hyfinnan.com/ | ESG评级数据 |
| **OpenAI** | OPENAI_API_KEY | https://platform.openai.com/account/api-keys | Fallback LLM |
| **DeepSeek** | DEEPSEEK_API_KEY | https://platform.deepseek.com/api/keys | Fallback LLM |
| **SEC** | SEC_EDGAR_EMAIL | https://www.sec.gov/cgi-bin/browse-edgar | 官方披露文件 |

### 📧 **邮件配置**（通知推送）

| 配置项 | 说明 | 示例 |
|--------|------|------|
| SMTP_SERVER | SMTP服务器 | smtp.gmail.com |
| SMTP_PORT | SMTP端口 | 587 |
| SMTP_USERNAME | 邮箱地址 | your_email@gmail.com |
| SMTP_PASSWORD | 邮箱密码 | Google应用专用密码 |

---

## ⚙️ 环境配置

### 步骤1: 复制并编辑.env文件

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑.env文件，填入你的API Key
vim .env
```

### 步骤2: .env文件的关键配置

```bash
# ════ LLM 配置 ════
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ════ 数据库配置 ════
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=eyJhbGciOiJIUzI1NiI...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiI...

# ════ 数据源API ════
ALPHA_VANTAGE_API_KEY=your_api_key
NEWSAPI_KEY=your_api_key
FINNHUB_API_KEY=your_api_key

# ════ 应用配置 ════
ENVIRONMENT=production  # 或 development
SERVER_PORT=8000
LOG_LEVEL=INFO

# ════ 报告调度 ════
DAILY_REPORT_TIME=06:00
WEEKLY_REPORT_TIME=08:00
MONTHLY_REPORT_TIME=09:00
```

### 步骤3: 验证配置

```bash
# 检查.env文件是否存在
test -f .env && echo "✓ .env文件已创建" || echo "✗ .env文件不存在"

# 验证关键配置项
grep "ANTHROPIC_API_KEY" .env && echo "✓ ANTHROPIC_API_KEY已配置"
grep "SUPABASE_URL" .env && echo "✓ SUPABASE_URL已配置"
```

---

## 💾 数据库设置

### 步骤1: 创建Supabase项目

1. 访问 [https://app.supabase.com](https://app.supabase.com)
2. 创建新项目（选择合适的地区）
3. 等待项目初始化完成（~1-2分钟）

### 步骤2: 获取数据库凭证

在Supabase仪表板中：
- **Project URL** → 复制到 `SUPABASE_URL`
- **Project API Key (anon)** → 复制到 `SUPABASE_API_KEY`
- **Service Role Secret** → 复制到 `SUPABASE_SERVICE_ROLE_KEY`

### 步骤3: 执行数据库迁移

```bash
# 方法A: 使用Supabase CLI（推荐）
supabase db push

# 方法B: 手动在Supabase SQL编辑器中执行
# 1. 进入 Supabase 仪表板 → SQL编辑器
# 2. 依次执行以下SQL文件：
#    - migrations/001_initial_schema.sql
#    - migrations/002_scheduler_tables.sql
#    - migrations/003_add_esg_report_tables.sql
```

### 步骤4: 验证数据库

```bash
# 检查表是否创建成功
psql -h your-project.supabase.co -U postgres -d postgres \
  -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
```

**应看到的表**:
- ✓ esg_events
- ✓ extracted_events
- ✓ risk_scores
- ✓ user_preferences
- ✓ esg_reports
- ✓ company_data_snapshot
- ✓ report_push_history
- ✓ push_rules
- ✓ user_report_subscriptions

---

## 📦 依赖安装

### 步骤1: 更新requirements.txt

新增的依赖包（应添加到requirements.txt）:

```
# 新增依赖
schedule==1.2.0              # 任务调度
pydantic==2.0.0              # 数据验证
supabase==2.0.0              # Supabase客户端
requests==2.31.0             # HTTP请求
transformers==4.30.0         # 模型库（可选，用于本地推理）
peft==0.4.0                  # LoRA微调（可选）
torch==2.0.0                 # PyTorch（可选，GPU支持）

# 已有依赖（确保版本兼容）
fastapi>=0.95.0
uvicorn>=0.21.0
python-dotenv>=1.0.0
pydantic>=2.0.0
langchain>=0.0.200
langgraph>=0.0.1
llama-index>=0.8.0
openai>=0.27.0
anthropic>=0.3.0
```

### 步骤2: 安装依赖

```bash
# 使用pip安装
pip install -r requirements.txt

# 或使用poetry（如果项目使用poetry）
poetry install
```

### 步骤3: 验证安装

```bash
# 测试关键包的导入
python -c "
import fastapi
import supabase
import anthropic
import pydantic
print('✓ 所有关键包安装成功')
"
```

---

## 🚀 项目启动

### 步骤1: 确保所有配置就绪

```bash
# 检查.env文件
test -f .env && echo "✓ .env配置就绪"

# 检查依赖
pip list | grep -E "fastapi|supabase|anthropic" && echo "✓ 依赖就绪"

# 检查数据库连接
python -c "
from gateway.db.supabase_client import supabase_client
print('✓ 数据库连接成功')
" 2>/dev/null || echo "✗ 数据库连接失败，请检查SUPABASE_URL和API Key"
```

### 步骤2: 启动应用

```bash
# 方法A: 直接运行（开发环境）
cd gateway
python main.py
# 应看到输出：
# INFO:     Uvicorn running on http://0.0.0.0:8000

# 方法B: 使用uvicorn（推荐）
cd gateway
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 方法C: 在后台运行（生产环境）
cd gateway
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

### 步骤3: 验证服务启动

```bash
# 检查健康状态
curl http://localhost:8000/health

# 预期响应:
# {
#   "status": "ok",
#   "timestamp": "2026-03-29T...",
#   "modules": {
#     "rag": true,
#     "esg_scorer": true,
#     "report_scheduler": true
#   }
# }
```

---

## ✅ 验证和测试

### 测试1: 被动分析（Agent工作流）

```bash
curl -X POST http://localhost:8000/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "分析特斯拉的ESG表现",
    "session_id": "test_session_001"
  }'
```

**预期响应**:
```json
{
  "question": "分析特斯拉的ESG表现",
  "answer": "特斯拉在ESG表现...",
  "esg_scores": {...},
  "confidence": 0.92,
  "analysis_summary": "..."
}
```

### 测试2: ESG评分（新功能）

```bash
curl -X POST http://localhost:8000/agent/esg-score \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Tesla",
    "ticker": "TSLA",
    "include_visualization": true
  }'
```

**预期响应**:
```json
{
  "esg_report": {
    "company_name": "Tesla",
    "overall_score": 78.5,
    "e_scores": {...},
    "s_scores": {...},
    "g_scores": {...}
  },
  "visualizations": {
    "radar": {...},
    "dimension_bars": {...},
    ...
  }
}
```

### 测试3: 生成报告（新功能）

```bash
curl -X POST http://localhost:8000/admin/reports/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "weekly",
    "companies": ["Tesla", "Apple"],
    "async": true
  }'
```

**预期响应**:
```json
{
  "report_id": "report_123456",
  "status": "generating",
  "report_type": "weekly"
}
```

### 测试4: 数据同步（新功能）

```bash
curl -X POST http://localhost:8000/admin/data-sources/sync \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["alpha_vantage", "newsapi"],
    "companies": ["TSLA", "AAPL"]
  }'
```

### 测试5: 推送规则（新功能）

```bash
curl -X POST http://localhost:8000/admin/push-rules \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "test_rule",
    "condition": "esg_score < 40",
    "target_users": "all",
    "push_channels": ["in_app", "email"],
    "priority": 5,
    "template_id": "template_test"
  }'
```

---

## 📚 完整的API测试脚本

```python
# test_api.py - 完整的API功能测试
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查"""
    print("[Test] Health Check...")
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    print("✓ Health check passed\n")

def test_esg_score():
    """测试ESG评分"""
    print("[Test] ESG Score...")
    payload = {
        "company": "Tesla",
        "ticker": "TSLA",
        "include_visualization": True
    }
    resp = requests.post(f"{BASE_URL}/agent/esg-score", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "esg_report" in data
    assert data["esg_report"]["overall_score"] > 0
    print(f"✓ ESG Score: {data['esg_report']['overall_score']}\n")

def test_report_generation():
    """测试报告生成"""
    print("[Test] Report Generation...")
    payload = {
        "report_type": "weekly",
        "companies": ["Tesla", "Apple"],
        "async_": True
    }
    resp = requests.post(f"{BASE_URL}/admin/reports/generate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "report_id" in data
    print(f"✓ Report ID: {data['report_id']}\n")

def test_push_rules():
    """测试推送规则"""
    print("[Test] Push Rules...")
    payload = {
        "rule_name": f"test_rule_{datetime.now().timestamp()}",
        "condition": "esg_score < 40",
        "target_users": "all",
        "push_channels": ["in_app"],
        "priority": 5,
        "template_id": "template_test"
    }
    resp = requests.post(f"{BASE_URL}/admin/push-rules", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "rule_id" in data
    print(f"✓ Rule ID: {data['rule_id']}\n")

if __name__ == "__main__":
    print("=" * 50)
    print("ESG Copilot API 功能测试")
    print("=" * 50 + "\n")

    try:
        test_health()
        test_esg_score()
        test_report_generation()
        test_push_rules()

        print("=" * 50)
        print("✓ 所有测试通过！")
        print("=" * 50)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
```

**运行测试**:
```bash
python test_api.py
```

---

## ❓ 常见问题

### Q1: "ANTHROPIC_API_KEY not found"

**原因**: 未设置环境变量

**解决方案**:
```bash
# 检查.env文件
grep ANTHROPIC_API_KEY .env

# 确保文件在项目根目录
ls -la .env

# 重新启动应用使配置生效
# (重新启动后load_dotenv会重新加载)
```

### Q2: "无法连接到数据库"

**原因**: Supabase URL或API Key不正确

**解决方案**:
```bash
# 验证Supabase配置
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('SUPABASE_URL:', os.getenv('SUPABASE_URL'))
print('Has API Key:', len(os.getenv('SUPABASE_API_KEY', '')) > 0)
"

# 测试连接
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-project.supabase.co/rest/v1/
```

### Q3: "报告生成失败"

**原因**: Alpha Vantage或其他数据源API未配置

**解决方案**:
```bash
# 检查数据源配置
grep ALPHA_VANTAGE .env
grep NEWSAPI .env
grep FINNHUB .env

# 不配置这些API也可以，系统会使用模拟数据
# 只是数据质量会下降
```

### Q4: "推送通知未发送"

**原因**: SMTP或邮件配置不正确

**解决方案**:
```bash
# 检查邮件配置
grep SMTP .env

# 使用应用专用密码（对于Gmail）
# 参考: https://support.google.com/accounts/answer/185833

# 测试邮件连接
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your_email@gmail.com', 'app_password')
print('✓ 邮件连接成功')
server.quit()
"
```

### Q5: "内存占用过高"

**原因**: 缓存数据量大或后台任务过多

**解决方案**:
```bash
# 清理缓存
python -c "
from gateway.utils.cache import clear_cache
clear_cache()
print('✓ 缓存已清理')
"

# 限制报告生成并发数
# 在 report_scheduler.py 中调整并发设置
```

---

## 📊 性能优化建议

### 1. 使用Redis缓存（可选）

```bash
# 安装Redis
brew install redis  # macOS
apt-get install redis-server  # Ubuntu

# 启动Redis
redis-server

# 在.env中配置
CACHE_TYPE=redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 2. 使用CDN分发静态资源

```nginx
# nginx配置示例
location /api {
    proxy_pass http://localhost:8000;
}

location /static {
    alias /path/to/static;
    expires 30d;
}
```

### 3. 数据库查询优化

```sql
-- 添加索引加速查询
CREATE INDEX idx_company_date ON company_data_snapshot(company_name, snapshot_date DESC);
CREATE INDEX idx_report_type ON esg_reports(report_type, generated_at DESC);
CREATE INDEX idx_user_push ON report_push_history(user_id, created_at DESC);
```

### 4. 异步任务处理

```python
# 使用Celery处理长时间任务（可选）
from celery import Celery

app = Celery('esg_copilot')
app.conf.broker_url = 'redis://localhost:6379/0'

@app.task
def generate_report_async(report_type, companies):
    # 后台生成报告
    pass
```

---

## 🔐 生产环境检查清单

- [ ] ✅ 所有API Key已配置且正确
- [ ] ✅ 数据库已创建所有表和视图
- [ ] ✅ 依赖包已安装且版本兼容
- [ ] ✅ .env文件已复制并填充（不提交到git）
- [ ] ✅ 日志级别已设置为INFO
- [ ] ✅ CORS已配置为允许前端域名
- [ ] ✅ 数据库备份策略已制定
- [ ] ✅ 监控和告警已配置
- [ ] ✅ SSL/TLS证书已配置
- [ ] ✅ 定期数据同步任务已启用
- [ ] ✅ 推送规则已创建和测试
- [ ] ✅ 邮件通知已测试

---

## 📞 技术支持

- 📖 详细API文档: [API_ENDPOINTS.md](./API_ENDPOINTS.md)
- 📋 增强方案: [ENHANCEMENT_PLAN.md](./ENHANCEMENT_PLAN.md)
- 📌 Scheduler文档: [SCHEDULER_README.md](./SCHEDULER_README.md)
- 🐛 问题报告: GitHub Issues
- 💬 讨论: GitHub Discussions

---

**祝贺！您已成功部署ESG Agentic RAG Copilot 🎉**

应用现在已准备好处理：
- ✓ 被动ESG分析查询
- ✓ 结构化15维度ESG评分
- ✓ 定期自动报告生成
- ✓ 多源数据融合
- ✓ 智能推送通知
- ✓ 用户个性化订阅

开始使用: `curl http://localhost:8000/health`
