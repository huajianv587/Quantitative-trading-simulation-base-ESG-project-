# ESG Agentic RAG Copilot - 完整API文档

**基础URL**: `http://localhost:8000` (开发环境) / `https://api.esg-copilot.com` (生产环境)

---

## 📊 目录

1. [Agent API](#agent-api---被动分析) - 用户查询接口
2. [ESG评分API](#esg评分api---强化的分析) - 结构化评分
3. [报告API](#报告api---定期报告系统) - 报告生成与查询
4. [数据源API](#数据源api---数据管理) - 数据拉取与同步
5. [推送规则API](#推送规则api---智能推送) - 推送规则管理
6. [用户订阅API](#用户订阅api---个性化订阅) - 用户订阅管理

---

## Quant API - ESG Quant 平台

### GET /api/v1/quant/platform/overview

返回整套 ESG Quant 平台总览，包括架构层、存储状态、信号预览、组合预览、最新回测和训练规划。

### POST /api/v1/quant/research/run

运行一轮 ESG Quant 研究流程。

请求示例:

```json
{
  "universe": ["AAPL", "MSFT", "TSLA"],
  "benchmark": "SPY",
  "research_question": "Generate an ESG quant shortlist.",
  "capital_base": 500000,
  "horizon_days": 15
}
```

### POST /api/v1/quant/portfolio/optimize

生成组合优化结果，返回持仓建议、约束和存储信息。

### POST /api/v1/quant/backtests/run

执行一轮回测，返回收益指标、时间线和风险告警。

### GET /api/v1/quant/backtests

查看历史回测记录。

### POST /api/v1/quant/execution/paper

生成 Paper Trading 执行清单。

Additional request fields for `/api/v1/quant/execution/paper`:

```json
{
  "submit_orders": false,
  "max_orders": 2,
  "per_order_notional": 1.0,
  "order_type": "market",
  "time_in_force": "day",
  "extended_hours": false
}
```

When `submit_orders=true` and Alpaca paper credentials are configured, the API will submit small paper orders and return broker receipts.

### GET /api/v1/quant/execution/account

Return Alpaca paper connection status, account snapshot, and market clock.

### GET /api/v1/quant/execution/orders

Return recent Alpaca paper orders.

### GET /api/v1/quant/execution/positions

Return current Alpaca paper positions.

### GET /api/v1/quant/experiments

查看最近的实验记录。

---

## Agent API - 被动分析

### POST /agent/analyze

**用户主动查询，返回ESG分析结果**

**请求**:
```bash
curl -X POST http://localhost:8000/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "question": "分析特斯拉的ESG表现",
    "session_id": "user_session_123"
  }'
```

**请求体**:
```json
{
  "question": "string (required) - 用户问题",
  "session_id": "string (optional) - 会话ID，用于保存对话历史"
}
```

**响应**:
```json
{
  "question": "分析特斯拉的ESG表现",
  "answer": "特斯拉在环境维度表现强劲...",
  "esg_scores": {
    "e_score": 78,
    "s_score": 65,
    "g_score": 72,
    "overall_score": 71.7
  },
  "confidence": 0.92,
  "analysis_summary": "综合评分：71.7/100，整体表现良好"
}
```

**状态码**:
- `200` - 成功
- `400` - 请求参数错误
- `500` - 服务器错误

---

## ESG评分API - 强化的分析

### POST /agent/esg-score

**生成完整的结构化ESG评分报告，包含可视化数据**

**请求**:
```bash
curl -X POST http://localhost:8000/agent/esg-score \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Tesla",
    "ticker": "TSLA",
    "include_visualization": true,
    "peers": ["Ford", "General Motors"],
    "historical_data": true
  }'
```

**请求体**:
```json
{
  "company": "string (required) - 公司名称",
  "ticker": "string (optional) - 股票代码",
  "include_visualization": "boolean (optional, default: true) - 是否包含可视化数据",
  "peers": "array[string] (optional) - 对标公司列表",
  "historical_data": "boolean (optional, default: false) - 是否包含历史数据"
}
```

**响应**:
```json
{
  "esg_report": {
    "company_name": "Tesla",
    "ticker": "TSLA",
    "industry": "Automotive",
    "overall_score": 78.5,
    "overall_trend": "up",
    "e_scores": {
      "dimension": "E",
      "overall_score": 85,
      "metrics": {
        "carbon_emissions": {
          "name": "碳排放强度",
          "score": 82,
          "weight": 0.25,
          "reasoning": "相比行业平均水平低20%",
          "trend": "down",
          "data_source": "SEC EDGAR"
        },
        "renewable_energy": {
          "name": "可再生能源使用",
          "score": 92,
          "weight": 0.20,
          "reasoning": "100%使用可再生能源",
          "trend": "up"
        }
        // ... 更多指标
      },
      "summary": "环保表现突出，在可再生能源和碳管理方面领先"
    },
    "s_scores": { /* 社会维度评分 */ },
    "g_scores": { /* 治理维度评分 */ },
    "key_strengths": [
      "✓ 可再生能源投资领先",
      "✓ 员工多样性持续改善",
      "✓ 治理结构清晰透明"
    ],
    "key_weaknesses": [
      "✗ 劳动关系仍需改进",
      "✗ 供应链伦理监管力度不足"
    ],
    "recommendations": [
      "强化供应链ESG审查机制",
      "增加女性高管比例",
      "提升社会投资透明度"
    ],
    "peer_rank": "top 15%",
    "industry_position": "领先同行",
    "assessment_date": "2026-03-29T10:30:00Z",
    "confidence_score": 0.94
  },
  "visualizations": {
    "radar": {
      "type": "radar",
      "title": "Tesla - ESG三维评分",
      "data": {
        "labels": ["环境(E)", "社会(S)", "治理(G)"],
        "datasets": [
          {
            "label": "Tesla",
            "data": [85, 70, 75]
          }
        ]
      }
    },
    "dimension_bars": { /* 柱状图数据 */ },
    "metric_details": { /* 指标详细表 */ },
    "heatmap": { /* 热力图数据 */ },
    "gauges": { /* 仪表盘数据 */ },
    "summary_stats": { /* 摘要统计 */ }
  }
}
```

**使用场景**:
- 前端需要显示企业的详细ESG评分
- 生成可视化报告
- 进行企业对标分析

---

## 报告API - 定期报告系统

### POST /admin/reports/generate

**主动生成各类报告**

**请求**:
```bash
curl -X POST http://localhost:8000/admin/reports/generate \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "weekly",
    "companies": ["Tesla", "Apple", "Microsoft"],
    "async": true
  }'
```

**请求体**:
```json
{
  "report_type": "string (required) - 报告类型: daily|weekly|monthly",
  "companies": "array[string] (required) - 公司列表",
  "async": "boolean (optional, default: true) - 是否异步生成",
  "include_peer_comparison": "boolean (optional) - 是否包含对标分析"
}
```

**响应**:
```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "generating",
  "report_type": "weekly",
  "companies_count": 3,
  "estimated_completion_time": "2026-03-29T10:50:00Z",
  "message": "报告生成中，请使用report_id查询进度"
}
```

---

### GET /admin/reports/{report_id}

**获取已生成的报告**

**请求**:
```bash
curl -X GET http://localhost:8000/admin/reports/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer {token}"
```

**响应**:
```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "report_type": "weekly",
  "title": "ESG 周度报告",
  "period_start": "2026-03-22T00:00:00Z",
  "period_end": "2026-03-29T23:59:59Z",
  "executive_summary": "本周监控的3家企业平均ESG评分为72.3/100，整体保持稳定趋势...",
  "key_findings": [
    "⚠️ 1家企业ESG评分低于40分，需要重点关注",
    "✓ 2家企业表现优秀，ESG评分80分以上"
  ],
  "company_analyses": [
    {
      "company_name": "Tesla",
      "ticker": "TSLA",
      "esg_score": 78.5,
      "score_change": 2.3,
      "trend": "up",
      "summary": "表现优秀，整体向上",
      "key_metrics": {
        "e_score": 85,
        "s_score": 70,
        "g_score": 75
      },
      "peer_rank": "top 15%"
    }
    // ... 更多公司分析
  ],
  "risk_alerts": [
    {
      "company": "Company X",
      "risk_level": "high",
      "category": "S",
      "title": "劳动关系事件",
      "description": "员工集体诉讼...",
      "impact": "可能影响品牌声誉",
      "recommendation": "立即与工会协商，准备应对方案",
      "alert_date": "2026-03-28T15:30:00Z"
    }
  ],
  "best_practices": [
    {
      "company": "Apple",
      "category": "E",
      "title": "碳中和承诺",
      "description": "2030年前实现碳中和，已完成50%目标",
      "impact": "树立行业标杆",
      "benchmark_score": 92
    }
  ],
  "report_statistics": {
    "total_companies": 3,
    "average_score": 72.3,
    "high_performers": 2,
    "low_performers": 1
  },
  "generated_at": "2026-03-29T09:45:00Z",
  "data_sources": ["esg_scorer", "data_sources", "news"],
  "confidence_score": 0.88
}
```

---

### GET /admin/reports/latest

**获取最新的报告**

**请求参数**:
```
?report_type=weekly  (required: daily|weekly|monthly)
?company=Tesla       (optional: 特定公司)
```

**响应**: 同上的报告完整结构

---

### GET /admin/reports/export/{report_id}

**导出报告为PDF/Excel格式**

**请求**:
```bash
curl -X GET "http://localhost:8000/admin/reports/550e8400-e29b-41d4-a716-446655440000/export?format=pdf" \
  -H "Authorization: Bearer {token}" \
  --output report.pdf
```

**查询参数**:
- `format`: `pdf` | `xlsx` | `json`

**响应**: 二进制文件或JSON数据

---

## 数据源API - 数据管理

### POST /admin/data-sources/sync

**触发从外部API拉取数据并同步到数据库**

**请求**:
```bash
curl -X POST http://localhost:8000/admin/data-sources/sync \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["alpha_vantage", "hyfinnan", "sec_edgar", "newsapi"],
    "companies": ["TSLA", "AAPL", "MSFT"],
    "force_refresh": false
  }'
```

**请求体**:
```json
{
  "sources": "array[string] (optional) - 数据源列表",
  "companies": "array[string] (required) - 公司代码或名称",
  "force_refresh": "boolean (optional, default: false) - 是否强制刷新缓存"
}
```

**响应**:
```json
{
  "job_id": "sync_job_123",
  "status": "started",
  "companies_to_sync": 3,
  "sources": ["alpha_vantage", "hyfinnan", "sec_edgar", "newsapi"],
  "estimated_duration_seconds": 120,
  "message": "数据同步已启动，使用job_id查询进度"
}
```

---

### GET /admin/data-sources/sync/{job_id}

**查询数据同步任务的进度**

**请求**:
```bash
curl -X GET http://localhost:8000/admin/data-sources/sync/sync_job_123 \
  -H "Authorization: Bearer {token}"
```

**响应**:
```json
{
  "job_id": "sync_job_123",
  "status": "completed",
  "start_time": "2026-03-29T09:00:00Z",
  "completion_time": "2026-03-29T09:02:15Z",
  "companies_synced": 3,
  "companies_failed": 0,
  "total_records": 450,
  "errors": [],
  "summary": {
    "alpha_vantage": "3/3 成功",
    "hyfinnan": "3/3 成功",
    "sec_edgar": "3/3 成功",
    "newsapi": "3/3 成功"
  }
}
```

---

## 推送规则API - 智能推送

### POST /admin/push-rules

**创建新的推送规则**

**请求**:
```bash
curl -X POST http://localhost:8000/admin/push-rules \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "warn_low_esg",
    "condition": "low_performer_count > 0",
    "target_users": "holders",
    "push_channels": ["email", "in_app"],
    "priority": 8,
    "template_id": "template_low_esg_warning"
  }'
```

**请求体**:
```json
{
  "rule_name": "string (required) - 规则名称，唯一",
  "condition": "string (required) - Python表达式条件",
  "target_users": "string (required) - all|holders|followers|analysts",
  "push_channels": "array[string] (required) - in_app|email|webhook",
  "priority": "integer (required) - 1-10，值越大优先级越高",
  "template_id": "string (required) - 推送模板ID"
}
```

**条件表达式示例**:
```
"esg_score < 40"
"high_performer_count > 0"
"overall_score < 30 and change < -5"
"low_performer_count > 2"
"report_type == 'daily' and risk_alert_count > 3"
```

**响应**:
```json
{
  "rule_id": "rule_550e8400-e29b-41d4-a716-446655440000",
  "rule_name": "warn_low_esg",
  "status": "created",
  "message": "推送规则已创建"
}
```

---

### GET /admin/push-rules

**获取所有推送规则**

**请求**:
```bash
curl -X GET http://localhost:8000/admin/push-rules \
  -H "Authorization: Bearer {token}"
```

**响应**:
```json
{
  "total": 5,
  "rules": [
    {
      "id": "rule_1",
      "rule_name": "warn_low_esg",
      "condition": "low_performer_count > 0",
      "target_users": "holders",
      "push_channels": ["email", "in_app"],
      "priority": 8,
      "template_id": "template_low_esg_warning",
      "enabled": true,
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-29T15:30:00Z"
    }
    // ... 更多规则
  ]
}
```

---

### PUT /admin/push-rules/{rule_id}

**更新推送规则**

**请求**:
```bash
curl -X PUT http://localhost:8000/admin/push-rules/rule_1 \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "condition": "low_performer_count > 1",
    "priority": 9,
    "enabled": false
  }'
```

**响应**:
```json
{
  "rule_id": "rule_1",
  "status": "updated",
  "message": "推送规则已更新"
}
```

---

### DELETE /admin/push-rules/{rule_id}

**删除推送规则**

**请求**:
```bash
curl -X DELETE http://localhost:8000/admin/push-rules/rule_1 \
  -H "Authorization: Bearer {token}"
```

**响应**:
```json
{
  "rule_id": "rule_1",
  "status": "deleted",
  "message": "推送规则已删除"
}
```

---

### POST /admin/push-rules/{rule_id}/test

**测试推送规则（基于真实已落库报告）**

**请求**:
```bash
curl -X POST http://localhost:8000/admin/push-rules/rule_1/test \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "test_user_id": "user_123"
  }'
```

默认行为会自动加载 `esg_reports` 中最近一份真实报告。也可以额外传入 `report_id`，只针对某一份真实报告测试：

```json
{
  "test_user_id": "user_123",
  "report_id": "report_20260423_001"
}
```

**响应**:
```json
{
  "test_id": "test_123",
  "rule_id": "rule_1",
  "status": "success",
  "report_id": "report_20260423_001",
  "report_type": "daily",
  "generated_at": "2026-04-23T08:12:00Z",
  "results": {
    "test_user_id": "user_123",
    "matched": true,
    "channels_tested": ["email", "in_app"]
  }
}
```

**无真实报告时的阻断响应**:
```json
{
  "test_id": "test_124",
  "rule_id": "rule_1",
  "status": "blocked",
  "report_id": null,
  "report_type": null,
  "generated_at": null,
  "block_reason": "real_report_required",
  "next_actions": [
    "Generate a real report",
    "Refresh reports",
    "Retry push-rule test"
  ],
  "results": {
    "test_user_id": "user_123",
    "matched": false,
    "channels_tested": ["email", "in_app"]
  }
}
```

---

## 用户订阅API - 个性化订阅

### POST /user/reports/subscribe

**用户订阅报告和推送**

**请求**:
```bash
curl -X POST http://localhost:8000/user/reports/subscribe \
  -H "Authorization: Bearer {user_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_types": ["weekly", "monthly"],
    "companies": ["Tesla", "Apple"],
    "alert_threshold": {
      "esg_score": 40,
      "score_change": -5
    },
    "push_channels": ["email", "in_app"],
    "frequency": "daily"
  }'
```

**请求体**:
```json
{
  "report_types": "array[string] (required) - daily|weekly|monthly",
  "companies": "array[string] (required) - 关注的公司",
  "alert_threshold": "object (optional) - 告警阈值",
  "push_channels": "array[string] (required) - in_app|email|webhook",
  "frequency": "string (optional, default: daily) - immediate|daily|weekly"
}
```

**响应**:
```json
{
  "subscription_id": "sub_user_123",
  "user_id": "user_123",
  "status": "subscribed",
  "subscribed_to": {
    "report_types": ["weekly", "monthly"],
    "companies": ["Tesla", "Apple"],
    "channels": ["email", "in_app"]
  },
  "message": "订阅已保存"
}
```

---

### GET /user/reports/subscriptions

**获取用户的订阅信息**

**请求**:
```bash
curl -X GET http://localhost:8000/user/reports/subscriptions \
  -H "Authorization: Bearer {user_token}"
```

**响应**:
```json
{
  "subscriptions": [
    {
      "subscription_id": "sub_user_123",
      "report_types": ["weekly", "monthly"],
      "companies": ["Tesla", "Apple"],
      "alert_threshold": {
        "esg_score": 40,
        "score_change": -5
      },
      "push_channels": ["email", "in_app"],
      "frequency": "daily",
      "subscribed_at": "2026-03-20T14:30:00Z",
      "updated_at": "2026-03-29T10:00:00Z"
    }
  ]
}
```

---

### PUT /user/reports/subscriptions/{subscription_id}

**更新用户订阅**

**请求**:
```bash
curl -X PUT http://localhost:8000/user/reports/subscriptions/sub_user_123 \
  -H "Authorization: Bearer {user_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "report_types": ["daily", "weekly"],
    "frequency": "weekly"
  }'
```

---

### DELETE /user/reports/subscriptions/{subscription_id}

**取消订阅**

**请求**:
```bash
curl -X DELETE http://localhost:8000/user/reports/subscriptions/sub_user_123 \
  -H "Authorization: Bearer {user_token}"
```

---

## 📊 报告统计API

### GET /admin/reports/statistics

**获取报告和推送的统计数据**

**请求**:
```bash
curl -X GET "http://localhost:8000/admin/reports/statistics?period=2026-03-01:2026-03-29&group_by=report_type" \
  -H "Authorization: Bearer {token}"
```

**查询参数**:
- `period`: 时间范围 `YYYY-MM-DD:YYYY-MM-DD`
- `group_by`: `report_type` | `company` | `push_channel`

**响应**:
```json
{
  "period": {
    "start": "2026-03-01",
    "end": "2026-03-29"
  },
  "total_reports": 30,
  "by_type": {
    "daily": 21,
    "weekly": 4,
    "monthly": 1
  },
  "push_statistics": {
    "total_notifications": 5400,
    "delivered": 5280,
    "read": 2640,
    "click_through_rate": 0.15,
    "avg_feedback_score": 4.2
  },
  "top_companies": [
    {"company": "Tesla", "reports": 15, "avg_score": 78.5},
    {"company": "Apple", "reports": 10, "avg_score": 82.1}
  ]
}
```

---

## 🔐 认证和授权

### 认证方法

**Bearer Token 认证** (所有需要认证的端点)

```bash
Authorization: Bearer {token}
```

### 获取Token

**登录获取Token** - 需要先实现认证接口

```bash
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 86400
}
```

### 权限等级

- **admin**: 可访问所有管理接口
- **analyst**: 可生成和查看报告
- **user**: 只能管理自己的订阅

---

## 📝 通知推送模板

### 可用的推送模板ID

| Template ID | 说明 | 用途 |
|------------|------|------|
| `template_low_esg_warning` | 低分预警 | ESG评分<40的企业 |
| `template_excellence` | 优秀案例 | ESG评分>80的企业 |
| `template_critical_alert` | 关键风险 | 评分<30或风险等级critical |
| `template_daily_digest` | 每日摘要 | 日报推送 |
| `template_weekly_summary` | 周度总结 | 周报推送 |
| `template_portfolio_review` | 投资组合评审 | 月报推送 |

---

## 错误处理

### 标准错误响应

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数错误详情",
    "details": {
      "field": "company",
      "reason": "公司名称不能为空"
    }
  }
}
```

### 常见错误代码

| 代码 | HTTP状态 | 说明 |
|-----|---------|------|
| INVALID_PARAMETER | 400 | 请求参数不合法 |
| UNAUTHORIZED | 401 | 未认证或Token过期 |
| FORBIDDEN | 403 | 无权限访问资源 |
| NOT_FOUND | 404 | 资源不存在 |
| CONFLICT | 409 | 资源冲突（如重复创建） |
| INTERNAL_ERROR | 500 | 服务器内部错误 |

---

## 使用示例

### 完整流程示例：生成周报并推送

```python
import requests
import json

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "your_admin_token"

# 1. 生成周报
response = requests.post(
    f"{BASE_URL}/admin/reports/generate",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    json={
        "report_type": "weekly",
        "companies": ["Tesla", "Apple", "Microsoft"],
        "async": True
    }
)
report_id = response.json()["report_id"]
print(f"Report ID: {report_id}")

# 2. 等待报告生成完成
import time
while True:
    response = requests.get(
        f"{BASE_URL}/admin/reports/{report_id}",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
    )
    if response.status_code == 200:
        report = response.json()
        print(f"Report Status: {report.get('generated_at')}")
        break
    time.sleep(5)

# 3. 推送规则已自动执行
print("Report generated and auto-pushed based on rules")

# 4. 查询推送统计
response = requests.get(
    f"{BASE_URL}/admin/reports/statistics?period=2026-03-20:2026-03-29",
    headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
)
stats = response.json()
print(f"推送统计: {json.dumps(stats, indent=2)}")
```

---

## 联系和支持

- 📖 完整文档: [SCHEDULER_README.md](./SCHEDULER_README.md)
- 🐛 问题报告: 使用GitHub Issues
- 💬 讨论: GitHub Discussions

