# ESG 系统增强方案 - 实现思路

**日期**: 2026-03-29
**核心目标**:
1. 强化 Analyst Agent 的结构化ESG指标评分 + 可视化
2. 构建主动报告系统：定期数据拉取 → 报告生成 → 智能推送

---

## 📊 方向一：强化 Analyst Agent（结构化评分 + 可视化）

### 1.1 新增 ESG 评分框架模块
**文件**: `gateway/agents/esg_scorer.py` (新建)

```python
# 核心功能：结构化的ESG评分体系
class ESGScoringFramework:
    def score_esg(self, company_name, esg_data) -> ESGScoreReport:
        """
        E/S/G 三维评分，包含：
        - 环境(E): 碳排放、能源效率、资源消耗、污染、生物多样性
        - 社会(S): 员工权益、多样性、供应链、社区关系、客户保护
        - 治理(G): 董事会结构、薪酬透明、反腐、风险管理、股东权益
        """
        return {
            "company": company_name,
            "e_score": {...},      # 环境维度详细评分
            "s_score": {...},      # 社会维度详细评分
            "g_score": {...},      # 治理维度详细评分
            "overall": 0-100,      # 综合评分
            "peer_rank": "top 20%", # 行业对标排名
            "trend": "↑↓→",        # 趋势
            "reasoning": "...",    # 推理过程
            "recommendations": []  # 改进建议
        }

# 数据结构
class ESGScoreReport:
    # E维度（5个指标）
    e_metrics = {
        "carbon_emissions": 0-100,      # 碳排放
        "energy_efficiency": 0-100,     # 能源效率
        "water_management": 0-100,      # 水资源管理
        "waste_management": 0-100,      # 废物管理
        "renewable_energy": 0-100       # 可再生能源使用
    }

    # S维度（5个指标）
    s_metrics = {
        "employee_satisfaction": 0-100, # 员工满意度
        "diversity_inclusion": 0-100,   # 多样性与包容性
        "supply_chain_ethics": 0-100,   # 供应链伦理
        "community_relations": 0-100,   # 社区关系
        "customer_protection": 0-100    # 客户保护
    }

    # G维度（5个指标）
    g_metrics = {
        "board_diversity": 0-100,       # 董事会多样性
        "executive_pay_ratio": 0-100,   # 高管薪酬合理性
        "anti_corruption": 0-100,       # 反腐机制
        "risk_management": 0-100,       # 风险管理
        "shareholder_rights": 0-100     # 股东权益保护
    }
```

### 1.2 新增可视化模块
**文件**: `gateway/agents/esg_visualizer.py` (新建)

```python
class ESGVisualizer:
    def generate_report_visual(self, esg_report: ESGScoreReport) -> dict:
        """
        生成多种可视化数据格式：
        1. Radar Chart (雷达图) - E/S/G三维
        2. Bar Charts - 各维度的5个指标
        3. Heatmap - 公司对标热力图
        4. Trend Chart - 时间序列变化
        5. Gauge Charts - 总体评分仪表
        """
        return {
            "radar": self._generate_radar_data(esg_report),
            "bars": self._generate_bar_charts(esg_report),
            "heatmap": self._generate_peer_heatmap(esg_report),
            "trends": self._generate_trend_chart(esg_report),
            "gauges": self._generate_gauge_charts(esg_report),
            "summary_html": self._generate_html_report(esg_report)
        }
```

### 1.3 更新 Analyst Agent
**修改**: `gateway/agents/agent.py` - Router → Retriever → **Analyst + ESGScorer** → Visualizer → Verifier

```
被动模式（Enhanced）:
  User Question
    ↓
  Router (分类：ESG评分查询)
    ↓
  Retriever (RAG检索该公司的ESG数据)
    ↓
  ESGScoringAgent (调用ESGScoringFramework)
    ↓
  ESGVisualizer (生成可视化)
    ↓
  Verifier (验证数据准确性)
    ↓
  Response (返回JSON + 可视化数据)
```

### 1.4 新增API端点
```python
# gateway/main.py - 新增
POST /agent/esg-score
{
    "company": "Tesla",
    "include_visualization": true,
    "peers": ["Ford", "GM"],  # 对标公司
    "historical_data": true   # 包含历史数据
}

Response:
{
    "esg_report": ESGScoreReport,
    "visualizations": {
        "radar": {...},
        "bars": {...},
        "heatmap": {...}
    },
    "peer_comparison": {...},
    "confidence": 0.92,
    "sources": [...]
}
```

---

## 📈 方向二：主动报告系统（定期数据拉取 + 报告生成 + 智能推送）

### 2.1 新增数据源集成模块
**文件**: `gateway/scheduler/data_sources.py` (新建)

```python
class DataSourceManager:
    """
    集成多个数据源的数据拉取器
    """

    def fetch_from_alpha_vantage(self, company_ticker: str) -> dict:
        """
        Alpha Vantage API:
        - 股价、市值、P/E比
        - 财务数据：收入、利润、现金流
        - 行业对标数据
        """
        pass

    def fetch_from_hyfinnan(self, company_name: str) -> dict:
        """
        Hyfinnan API (或替代品如Bloomberg, Refinitiv):
        - ESG评级数据
        - 可持续性报告
        - 第三方评分
        """
        pass

    def fetch_from_sec_edgar(self, company_name: str) -> dict:
        """
        SEC EDGAR:
        - 10-K 年报
        - 8-K 重大事件
        - DEF 14A 代理声明 (包含薪酬、董事信息)
        """
        pass

    def fetch_from_news_apis(self, company_name: str, keywords: list) -> list:
        """
        新闻来源：
        - Finnhub / NewsAPI
        - RSS feeds
        - 社交媒体
        """
        pass

# 统一数据模型
class CompanyData:
    company_name: str
    ticker: str
    industry: str
    market_cap: float

    # ESG数据
    esg_data: ESGScoreReport

    # 财务数据
    financial_metrics: {
        "revenue": float,
        "profit": float,
        "cash_flow": float,
        "debt_ratio": float,
        "roa": float,
        "roe": float
    }

    # 新闻事件
    recent_news: list[NewsEvent]

    # 外部评分
    external_ratings: {
        "msci_rating": str,
        "refinitiv_score": float,
        "sustainalytics_score": float
    }

    last_updated: datetime
```

### 2.2 新增报告生成模块
**文件**: `gateway/scheduler/report_generator.py` (新建)

```python
class ESGReportGenerator:
    """
    定期生成ESG风险报告（日/周/月）
    """

    def generate_daily_digest(self, user_preferences: UserPreference) -> ESGReport:
        """
        每日简报：
        - 关注公司的ESG新闻摘要
        - 风险预警
        - 优秀案例
        """
        pass

    def generate_weekly_report(self, companies: list[str]) -> ESGReport:
        """
        周报：
        - ESG评分变化
        - 行业对标分析
        - 风险热力图
        - 投资建议
        """
        pass

    def generate_monthly_report(self, portfolio: list[str]) -> PortfolioESGReport:
        """
        月报（投资组合视图）：
        - 整体ESG表现评分
        - 高风险公司预警
        - 优秀公司推荐
        - 行业趋势分析
        - 监管合规检查
        """
        pass

    def generate_peer_comparison(self, target_company: str, peers: list[str]) -> ComparisonReport:
        """
        对标分析：
        - ESG三维对比
        - 财务对比
        - 排名变化
        - 差距分析
        """
        pass

# 报告数据结构
class ESGReport:
    report_type: str  # "daily", "weekly", "monthly"
    period: tuple     # (start_date, end_date)

    # 核心内容
    summary: str      # 中文摘要
    executive_summary: dict  # 关键指标总结

    # 细节数据
    company_analyses: list[CompanyAnalysis]
    risk_alerts: list[RiskAlert]
    best_practices: list[BestPractice]

    # 可视化
    charts_data: dict  # 用于前端渲染

    # 源数据引用
    sources: list[str]

    generated_at: datetime

# 预警信息
class RiskAlert:
    company: str
    risk_level: str      # "critical", "high", "medium"
    category: str        # "E"/"S"/"G"

    title: str
    description: str
    impact: str          # 可能的影响
    recommendation: str  # 建议行动

    affected_areas: list[str]
```

### 2.3 新增调度和推送模块
**文件**: `gateway/scheduler/report_scheduler.py` (新建)

```python
class ReportScheduler:
    """
    自动化报告生成和推送调度
    """

    def schedule_reports(self):
        """
        设置定期报告任务：
        - 每日06:00 - 生成日报（提取新闻+风险）
        - 每周一08:00 - 生成周报（评分变化+对标）
        - 每月1日09:00 - 生成月报（投资组合视图）
        """
        pass

    def generate_and_push_report(self, report_type: str):
        """
        1. 批量拉取数据 (Alpha Vantage, Hyfinnan, SEC EDGAR)
        2. 调用ESGScoringFramework重新评分
        3. 生成ReportGenerator报告
        4. 智能推送
        """
        pass

    def intelligent_push(self, report: ESGReport, users: list[str]):
        """
        智能推送逻辑：
        - 优秀报告（ESG > 80）→ 推送给所有用户
        - 低分预警（ESG < 40）→ 推送给持有该股票的用户
        - 风险突变（评分-5以上）→ 推送给关注者
        - 行业热点 → 推送给行业分析师
        """
        pass

# 推送规则
class PushRule:
    condition: str      # Python表达式，如 "esg_score < 40 and change < -5"
    target_users: str   # "all", "holders", "followers", "analysts"
    push_channels: list # ["in_app", "email", "webhook"]
    priority: int       # 1-10
    template: str       # 推送模板ID
```

### 2.4 数据库扩展
**新增表**:
```sql
-- ESG报告表
CREATE TABLE esg_reports (
    id UUID PRIMARY KEY,
    report_type VARCHAR(20),  -- "daily", "weekly", "monthly"
    period_start DATE,
    period_end DATE,

    -- 报告内容（JSON）
    summary TEXT,
    data JSONB,
    visualizations JSONB,

    -- 元数据
    generated_at TIMESTAMP,
    data_source_version VARCHAR(50),

    UNIQUE(report_type, period_start, period_end)
);

-- 公司数据缓存（用于性能优化）
CREATE TABLE company_data_snapshot (
    id UUID PRIMARY KEY,
    company_name VARCHAR(255),
    ticker VARCHAR(10),

    -- ESG数据
    esg_score_report JSONB,

    -- 财务数据
    financial_metrics JSONB,

    -- 外部评分
    external_ratings JSONB,

    -- 时间戳
    snapshot_date DATE,
    last_updated TIMESTAMP,

    UNIQUE(company_name, snapshot_date)
);

-- 报告推送历史
CREATE TABLE report_push_history (
    id UUID PRIMARY KEY,
    report_id UUID REFERENCES esg_reports(id),
    user_id VARCHAR(255),

    push_channels TEXT[],
    push_status VARCHAR(20),  -- "sent", "failed", "pending"

    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    click_through BOOLEAN,

    feedback_score INT,  -- 用户反馈评分

    UNIQUE(report_id, user_id)
);

-- 推送规则表
CREATE TABLE push_rules (
    id UUID PRIMARY KEY,
    rule_name VARCHAR(255),

    condition TEXT,  -- 规则条件
    target_users VARCHAR(50),
    push_channels TEXT[],

    priority INT,
    template_id VARCHAR(255),

    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 2.5 新增API端点

```python
# 1. 数据源管理
POST /admin/data-sources/sync
{
    "sources": ["alpha_vantage", "hyfinnan", "sec_edgar"],
    "companies": ["TSLA", "AAPL", "MSFT"],
    "force_refresh": true
}
Response: { "job_id": "...", "status": "started" }

GET /admin/data-sources/sync/{job_id}
Response: { "status": "completed", "companies_synced": 10, "errors": [] }

# 2. 报告管理
POST /admin/reports/generate
{
    "report_type": "weekly",  # "daily", "weekly", "monthly"
    "companies": ["TSLA", "AAPL"],
    "async": true
}
Response: { "report_id": "...", "status": "generating" }

GET /admin/reports/{report_id}
Response: {
    "report": ESGReport,
    "visualizations": {...},
    "download_url": "..."
}

GET /admin/reports/latest
Query: ?report_type=weekly&company=TSLA
Response: ESGReport

# 3. 推送规则管理
POST /admin/push-rules
{
    "rule_name": "warn_low_esg",
    "condition": "esg_score < 40 AND esg_change < -5",
    "target_users": "holders",
    "push_channels": ["email", "in_app"],
    "priority": 8
}
Response: { "rule_id": "..." }

GET /admin/push-rules
Response: [PushRule, ...]

PUT /admin/push-rules/{rule_id}
POST /admin/push-rules/{rule_id}/test

# 4. 报告统计
GET /admin/reports/statistics
{
    "period": "2026-03-01:2026-03-29",
    "group_by": "report_type"
}
Response: {
    "total_reports": 30,
    "by_type": {"daily": 21, "weekly": 4, "monthly": 1},
    "avg_push_per_report": 450,
    "click_through_rate": 0.12
}

# 5. 用户订阅
POST /user/reports/subscribe
{
    "report_types": ["weekly", "monthly"],
    "companies": ["TSLA", "AAPL"],
    "alert_threshold": {"esg_score": 40, "change": -5},
    "push_channels": ["email", "in_app"],
    "frequency": "weekly"  # 推送频率
}

GET /user/reports/subscriptions
Response: [Subscription, ...]

# 6. 报告下载和分享
GET /user/reports/{report_id}
Response: { "report": ESGReport, ... }

GET /user/reports/{report_id}/export
Query: ?format=pdf|xlsx|json
Response: 文件下载

POST /user/reports/{report_id}/share
{
    "share_with": ["user2@example.com"],
    "expiry_days": 7
}
```

---

## 🏗️ 整体架构对比

### 当前架构 vs 增强架构

```
当前 (被动+主动):
Scanner → EventExtractor → RiskScorer → Matcher → Notifier
           (简单事件)      (通用评分)   (偏好匹配) (推送)

↓ Router → Retriever → Analyst → Verifier
  (用户查询)                    (简单分析)

增强后 (三层系统):
1️⃣ 数据层：
   ↓
   DataSourceManager (Alpha Vantage, Hyfinnan, SEC EDGAR)
   ↓
   CompanyDataSnapshot (缓存)

2️⃣ 分析层：
   ↓
   ESGScoringFramework (结构化评分)
   ↓
   ReportGenerator (定期报告)
   ↓
   ESGVisualizer (可视化)

3️⃣ 推送层：
   ↓
   ReportScheduler + PushRules (智能推送)
   ↓
   Notifier (多渠道)
```

---

## 📝 实现优先级和工期

### Phase 1 (第1周) - 基础框架
- [ ] `ESGScoringFramework` - 结构化评分框架
- [ ] `ESGVisualizer` - 可视化数据生成
- [ ] 更新 Analyst Agent 集成
- [ ] 新增 `/agent/esg-score` API

**工期**: 3-4天

### Phase 2 (第2周) - 数据集成
- [ ] `DataSourceManager` - 集成Alpha Vantage + Hyfinnan
- [ ] `CompanyDataSnapshot` - 数据缓存表
- [ ] 数据定期刷新任务

**工期**: 3-4天

### Phase 3 (第3周) - 报告系统
- [ ] `ReportGenerator` - 日/周/月报生成
- [ ] `ReportScheduler` - 定期调度
- [ ] 报告相关的数据库表和API
- [ ] 报告下载/分享功能

**工期**: 3-4天

### Phase 4 (第4周) - 推送优化
- [ ] `PushRules` - 智能推送规则引擎
- [ ] 推送规则管理 API
- [ ] 用户订阅管理
- [ ] 端到端测试和优化

**工期**: 3-4天

---

## 💡 技术亮点

### 1. 结构化评分体系
- 15个明确的指标（E/S/G各5个）
- 每个指标有独立权重和评分逻辑
- 支持行业对标和历史对比
- 推理过程透明化

### 2. 多源数据融合
- Alpha Vantage：财务和股价数据
- Hyfinnan/Bloomberg：ESG评级数据
- SEC EDGAR：官方披露文件
- 新闻API：实时事件监测
- → 数据一致性校验和去重

### 3. 智能报告推送
- 规则引擎支持复杂条件
- 基于用户偏好和持仓的个性化推送
- 推送效果跟踪（CTR、反馈）
- A/B测试框架预留

### 4. 可视化和导出
- 前端渲染数据（JSON格式）
- PDF/Excel报告生成
- 交互式对标分析
- 时间序列趋势展示

---

## 🔌 集成建议

### 与现有系统的连接点

```python
# 1. Analyst Agent 增强
from gateway.agents.esg_scorer import ESGScoringFramework
from gateway.agents.esg_visualizer import ESGVisualizer

# 在 agent.py 中
if question_type == "esg_score":
    scorer = ESGScoringFramework()
    esg_report = scorer.score_esg(company_name, data)

    visualizer = ESGVisualizer()
    visualizations = visualizer.generate_report_visual(esg_report)

    return {
        "report": esg_report,
        "visuals": visualizations
    }

# 2. Scheduler 增强
from gateway.scheduler.report_generator import ReportGenerator
from gateway.scheduler.report_scheduler import ReportScheduler

# 在 orchestrator.py 中添加报告流程
report_gen = ReportGenerator()
report = report_gen.generate_weekly_report(company_list)

report_scheduler = ReportScheduler()
report_scheduler.intelligent_push(report, target_users)

# 3. 数据源集成
from gateway.scheduler.data_sources import DataSourceManager

data_mgr = DataSourceManager()
company_data = data_mgr.fetch_from_alpha_vantage("TSLA")
esg_data = data_mgr.fetch_from_hyfinnan("Tesla")
```

---

## 📊 关键指标和检验

### 系统指标
- ESG评分覆盖率：15个指标完整评分
- 报告生成延迟：<5分钟（日报）
- 数据新鲜度：<24小时
- 推送准确率：>90%（用户偏好匹配）

### 业务指标
- 日活报告用户数
- 报告点击率（CTR）
- 用户反馈评分
- 推送失败率

---

## 总结

这个增强方案将系统从"事件监控"升级到"主动分析"：

1. **强化分析能力**：从模糊打分 → 15个维度的结构化评分
2. **自动化报告**：从被动查询 → 定期自动生成报告
3. **智能推送**：从简单通知 → 基于规则的个性化推送
4. **数据融合**：从单一来源 → 多源数据（财务+ESG+新闻）
5. **可视化展示**：从纯文本 → 图表和报告

预期可以在**4周内**完成全部实现，系统复杂度为中等，重点是数据集成和推送规则的精细化。
