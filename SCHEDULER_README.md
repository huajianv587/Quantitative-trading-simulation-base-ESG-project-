# ESG 调度器系统使用指南

这个文档说明如何使用 ESG Agentic RAG Copilot 的主动扫描和推送系统。

## 系统架构

```
┌─────────────┐
│  Scanner    │ ← 扫描新的 ESG 事件（新闻、报告、法规）
└──────┬──────┘
       ↓
┌─────────────────────┐
│ EventExtractor      │ ← 用 LLM 提取结构化信息
└──────┬──────────────┘
       ↓
┌──────────────────────┐
│ RiskScorer           │ ← 用 LLM 评分风险等级
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│ EventMatcher         │ ← 匹配用户偏好
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│ Notifier             │ ← 推送给相关用户
└──────────────────────┘
```

## 核心模块

### 1. Scanner（扫描器）
**文件**: `gateway/scheduler/scanner.py`

职责：定期扫描外部数据源，检测新的 ESG 事件。

**支持的数据源**：
- 新闻 API (News feeds, 如 Alpha Vantage)
- ESG 报告库 (SEC EDGAR, Bloomberg)
- 法规更新 (Government regulations, compliance updates)

**使用方式**：
```python
from gateway.scheduler.scanner import get_scanner

scanner = get_scanner()
result = scanner.run_scan()
print(f"Found {result['total_events']} events")
```

### 2. EventExtractor（事件提取器）
**文件**: `gateway/scheduler/event_extractor.py`

职责：使用 LLM 从原始文本中提取结构化信息，包括：
- 事件标题和描述
- 受影响公司
- 事件类型（E/S/G）
- 关键指标
- 严重性等级

**使用方式**：
```python
from gateway.scheduler.event_extractor import get_extractor

extractor = get_extractor()
result = extractor.process_new_events(event_ids)
print(f"Extracted {result['extracted']} events")
```

### 3. EventMatcher（事件匹配器）
**文件**: `gateway/scheduler/matcher.py`

职责：根据用户偏好和关注，筛选相关的 ESG 事件。

**匹配规则**：
1. **公司过滤** - 用户关注的公司清单
2. **类别过滤** - E（环境）/ S（社会）/ G（治理）
3. **严重性过滤** - 仅推送达到阈值的事件
4. **关键词过滤** - 自定义关键词匹配

**使用方式**：
```python
from gateway.scheduler.matcher import get_matcher

matcher = get_matcher()

# 创建或更新用户偏好
matcher.create_or_update_preference(
    user_id="user_123",
    preferences={
        "interested_companies": ["Tesla", "Microsoft", "Apple"],
        "interested_categories": ["E", "S"],  # 关注环境和社会
        "risk_threshold": "medium",           # 仅推送中等及以上风险
        "keywords": ["carbon", "renewable", "diversity"],
        "notification_channels": ["email", "in_app"],
    }
)

# 匹配事件
result = matcher.match_batch_events(event_ids)
print(f"Matched {result['total_matches']} event-user pairs")
```

### 4. RiskScorer（风险评分器）
**文件**: `gateway/scheduler/risk_scorer.py`

职责：使用 LLM 对事件进行深度风险评分。

**评分维度**：
- 风险等级：low / medium / high / critical
- 风险分数：0-100
- 受影响维度：E/S/G 权重分布
- 建议行动

**使用方式**：
```python
from gateway.scheduler.risk_scorer import get_risk_scorer

scorer = get_risk_scorer()
result = scorer.score_batch_events(event_ids)
print(f"Scored {result['scored']} events")

# 获取最高风险事件
top_risks = scorer.get_top_risks(limit=10)
for risk in top_risks:
    print(f"{risk['title']}: {risk['score']}/100 ({risk['risk_level']})")
```

### 5. Notifier（推送器）
**文件**: `gateway/scheduler/notifier.py`

职责：根据用户偏好，通过多渠道推送通知。

**支持的推送渠道**：
- 📧 Email（邮件）
- 📱 In-app（应用内）
- 🔗 Webhook（第三方集成）

**使用方式**：
```python
from gateway.scheduler.notifier import get_notifier

notifier = get_notifier()

# 为一个事件推送通知给所有匹配的用户
result = notifier.send_notifications(event_id, user_ids)
print(f"Sent {result['sent']} notifications")
```

### 6. SchedulerOrchestrator（调度编排器）
**文件**: `gateway/scheduler/orchestrator.py`

职责：协调所有模块的执行，控制整个流程。

**主要功能**：
- 执行完整的扫描→分析→推送流程
- 定期调度扫描任务
- 收集执行统计

**使用方式**：
```python
from gateway.scheduler.orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# 执行一次完整流程
result = orchestrator.run_full_pipeline()

# 获取最近的扫描状态
status = orchestrator.get_scan_status()

# 获取 7 天内的统计
stats = orchestrator.get_pipeline_statistics(days=7)
print(f"Scanned: {stats['total_scanned']}, Notified: {stats['total_notified']}")

# 后台定期扫描（每 30 分钟）
orchestrator.schedule_periodic_scan_background(interval_minutes=30)
```

## 数据模型

### ESGEvent（原始事件）
```python
{
    "id": "uuid",
    "title": "Tesla Announces 50% Carbon Reduction Target",
    "description": "...",
    "company": "Tesla",
    "event_type": "emission_reduction",
    "source": "news_api",
    "source_url": "https://...",
    "detected_at": "2026-03-29T12:00:00Z",
    "raw_content": "...",
}
```

### ExtractedEvent（提取后的事件）
```python
{
    "id": "uuid",
    "original_event_id": "uuid",
    "title": "Tesla Announces 50% Carbon Reduction Target",
    "company": "Tesla",
    "event_type": "emission_reduction",
    "key_metrics": {
        "carbon_reduction": "50%",
        "target_year": "2030"
    },
    "impact_area": "E",
    "severity": "high",
}
```

### RiskScore（风险评分）
```python
{
    "id": "uuid",
    "event_id": "uuid",
    "risk_level": "high",
    "score": 78.5,
    "reasoning": "Major commitment from large cap company impacts market...",
    "affected_dimensions": {
        "environmental": 0.9,
        "social": 0.3,
        "governance": 0.2
    },
    "recommendation": "Positive ESG signal, monitor implementation progress",
}
```

### UserPreference（用户偏好）
```python
{
    "user_id": "user_123",
    "interested_companies": ["Tesla", "Microsoft"],
    "interested_categories": ["E", "S"],
    "risk_threshold": "medium",
    "keywords": ["carbon", "renewable"],
    "notification_channels": ["email", "in_app"],
}
```

## API 端点

### 触发扫描
```bash
POST /scheduler/scan

Response:
{
    "status": "scanning",
    "message": "ESG scan pipeline started in background",
    "timestamp": "2026-03-29T12:00:00Z"
}
```

### 获取扫描状态
```bash
GET /scheduler/scan/status

Response:
{
    "status": "completed",
    "data": {
        "job_type": "full_pipeline",
        "status": "completed",
        "events_found": 15,
        ...
    }
}
```

### 获取统计信息
```bash
GET /scheduler/statistics?days=7

Response:
{
    "period_days": 7,
    "statistics": {
        "total_scanned": 47,
        "total_extracted": 42,
        "total_scored": 40,
        "total_notified": 125,
        "success_rate": 89.36
    }
}
```

### 主动查询 ESG 分析
```bash
POST /agent/analyze?question=分析特斯拉的ESG表现&session_id=...

Response:
{
    "question": "分析特斯拉的ESG表现",
    "answer": "根据最新数据...",
    "esg_scores": {
        "environmental": {"score": 85, ...},
        "social": {"score": 72, ...},
        "governance": {"score": 80, ...},
        "overall_score": 79,
        "risk_level": "medium"
    },
    "confidence": 0.92,
    "analysis_summary": "..."
}
```

## 测试

运行完整的集成测试：
```bash
# 运行完整流程
python test_scheduler.py --full

# 仅测试扫描器
python test_scheduler.py --scanner

# 仅测试提取器
python test_scheduler.py --extractor

# 按顺序测试所有模块
python test_scheduler.py --scanner --extractor --matcher --scorer --notifier
```

## 环境变量配置

在 `.env` 文件中配置：

```bash
# ── LLM APIs ───────────────────────────────────────────
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...

# ── Supabase (Database) ────────────────────────────────
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
SUPABASE_PASSWORD=...

# ── Email Notifications ────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@esg-system.com

# ── Data Source APIs ───────────────────────────────────
ALPHA_VANTAGE_KEY=...
NEWS_API_KEY=...

# ── Scheduler Config ───────────────────────────────────
SCAN_INTERVAL_MINUTES=30
MAX_SCAN_RESULTS=100
DEBUG=True
```

## 数据库表设计

所需的 Supabase 表：

```sql
-- ESG 事件（原始）
CREATE TABLE esg_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    company TEXT,
    event_type TEXT,
    source TEXT,
    source_url TEXT,
    detected_at TIMESTAMPTZ,
    raw_content TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 提取的事件（结构化）
CREATE TABLE extracted_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_event_id UUID REFERENCES esg_events(id),
    title TEXT NOT NULL,
    description TEXT,
    company TEXT,
    event_type TEXT,
    key_metrics JSONB,
    impact_area TEXT,
    severity TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 风险评分
CREATE TABLE risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES extracted_events(id),
    risk_level TEXT,
    score FLOAT,
    reasoning TEXT,
    affected_dimensions JSONB,
    recommendation TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 用户偏好
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT UNIQUE NOT NULL,
    interested_companies TEXT[],
    interested_categories TEXT[],
    risk_threshold TEXT,
    keywords TEXT[],
    notification_channels TEXT[],
    email TEXT,
    webhook_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 事件-用户匹配
CREATE TABLE event_user_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES extracted_events(id),
    user_id TEXT,
    matched_at TIMESTAMPTZ DEFAULT now()
);

-- 应用内通知
CREATE TABLE in_app_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    title TEXT,
    content TEXT,
    severity TEXT,
    action_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    read_at TIMESTAMPTZ
);

-- 通知日志
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES extracted_events(id),
    user_id TEXT,
    channel TEXT,
    status TEXT,
    sent_at TIMESTAMPTZ
);

-- 扫描任务记录
CREATE TABLE scan_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT,
    status TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    events_found INT,
    errors TEXT[],
    last_cursor TEXT
);
```

## 工作流程示例

### 完整的主动推送流程：

1. **扫描** (15:00)
   - Scanner 扫描新闻、报告、法规
   - 发现 20 个新事件

2. **提取** (15:05)
   - EventExtractor 用 LLM 提取结构化信息
   - 成功提取 18 个事件

3. **评分** (15:15)
   - RiskScorer 评分每个事件
   - 3 个高风险，8 个中风险，7 个低风险

4. **匹配** (15:20)
   - EventMatcher 找出关注相关公司和类别的用户
   - 总共 150 个用户匹配

5. **推送** (15:25)
   - Notifier 推送给 150 个用户
   - 100 个通过邮件，50 个通过应用内

## 监控和调试

查看日志：
```bash
# 启用 DEBUG 模式查看详细日志
export DEBUG=True

# 运行服务
python -m gateway.main
```

监控指标：
```python
from gateway.scheduler.orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# 查看最近一次扫描
status = orchestrator.get_scan_status()
print(status)

# 查看 7 天统计
stats = orchestrator.get_pipeline_statistics(days=7)
print(f"Success rate: {stats['success_rate']:.1f}%")
```

## 故障排除

### 扫描返回空结果
- 检查数据源 API 密钥是否配置
- 检查网络连接
- 检查日志中的错误消息

### LLM 提取失败
- 提高 `max_retries` 值
- 检查 LLM 配额和费用
- 尝试使用不同的 LLM 模型

### 用户未收到通知
- 检查 `user_preferences` 表配置
- 检查通知渠道是否启用
- 检查邮箱/webhook 配置

## 性能优化

1. **缓存** - 使用 Redis 缓存相同问题的检索结果
2. **批处理** - 一次处理多个事件而不是逐个处理
3. **异步** - 在后台执行长时间操作
4. **断点续传** - 保存游标避免重复处理

## 扩展建议

1. **更多数据源** - 集成 RSS feeds、Slack、Discord
2. **更多 LLM** - 支持 Claude、GPT-4o、本地模型切换
3. **ML 排序** - 基于用户历史反馈的个性化排序
4. **A/B 测试** - 对通知内容和时间进行 A/B 测试
5. **导出** - 支持导出到 Excel、CSV、PDF

---

**更新日期**: 2026-03-29
**版本**: 1.0
