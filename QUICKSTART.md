# 快速开始指南

## 5 分钟快速上手 ESG 调度器系统

### 第一步：环境准备

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建 .env 文件
cp .env.example .env

# 3. 配置必需的环境变量
# 至少需要：
#   SUPABASE_URL=...
#   SUPABASE_KEY=...
#   OPENAI_API_KEY=... (或其他 LLM)
```

### 第二步：运行演示

```bash
# 看看系统能做什么
python demo_scheduler.py

# 你应该看到：
# ✓ 数据扫描演示
# ✓ 用户偏好管理演示
# ✓ 完整流程演示
# ✓ API 使用示例
# ✓ 统计数据示例
```

### 第三步：启动 API 服务

```bash
# 启动 FastAPI 服务器
python -m gateway.main

# 服务将在 http://localhost:8000 运行
```

### 第四步：调用 API

在另一个终端运行：

```bash
# 触发扫描
curl -X POST http://localhost:8000/scheduler/scan

# 检查扫描状态
curl http://localhost:8000/scheduler/scan/status

# 获取统计数据
curl http://localhost:8000/scheduler/statistics?days=7

# 进行 ESG 分析
curl -X POST "http://localhost:8000/agent/analyze?question=分析特斯拉的ESG表现&session_id=demo"
```

## 核心概念

### 主动模式 vs 被动模式

**主动模式**（系统主动发现）:
```
系统定期扫描 ESG 数据源
       ↓
自动识别新事件和风险
       ↓
推送给感兴趣的用户
       ↓
用户接收实时更新
```

**被动模式**（用户查询）:
```
用户提出问题
       ↓
系统分析和检索
       ↓
返回结构化答案
       ↓
用户获得见解
```

## 快速集成示例

### 在 Python 代码中使用

```python
from gateway.scheduler.orchestrator import get_orchestrator
from gateway.scheduler.matcher import get_matcher

# 设置用户偏好
matcher = get_matcher()
matcher.create_or_update_preference(
    user_id="user_123",
    preferences={
        "interested_companies": ["Tesla", "Microsoft"],
        "interested_categories": ["E", "S"],  # 环境和社会
        "risk_threshold": "medium",
        "keywords": ["carbon", "renewable"],
        "notification_channels": ["email", "in_app"],
    }
)

# 运行一次完整扫描
orchestrator = get_orchestrator()
result = orchestrator.run_full_pipeline()

print(f"发现了 {result['stages']['scan']['total_events']} 个事件")
print(f"推送了 {result['stages']['notify']['total_notifications']} 条通知")
```

### 在 FastAPI 中使用

```python
from fastapi import FastAPI, BackgroundTasks
from gateway.scheduler.orchestrator import get_orchestrator

app = FastAPI()

@app.post("/trigger-scan")
def trigger_scan(background_tasks: BackgroundTasks):
    orchestrator = get_orchestrator()
    # 后台执行，不阻塞 HTTP 响应
    background_tasks.add_task(orchestrator.run_full_pipeline)
    return {"status": "scanning"}
```

## 常见任务

### 创建用户偏好

```python
from gateway.scheduler.matcher import get_matcher

matcher = get_matcher()
matcher.create_or_update_preference(
    user_id="alice@company.com",
    preferences={
        "interested_companies": ["Apple", "Google"],
        "interested_categories": ["E", "G"],
        "risk_threshold": "high",  # 只推送高风险事件
        "keywords": ["carbon", "governance"],
        "notification_channels": ["email"],
    }
)
```

### 获取高风险事件

```python
from gateway.scheduler.risk_scorer import get_risk_scorer

scorer = get_risk_scorer()

# 获取所有"critical"级别的事件
critical_risks = scorer.get_risks_by_level("critical", limit=10)

for risk in critical_risks:
    print(f"{risk['title']}: 分数 {risk['score']}/100")
```

### 手动执行流程

```python
from gateway.scheduler.scanner import get_scanner
from gateway.scheduler.event_extractor import get_extractor
from gateway.scheduler.risk_scorer import get_risk_scorer

# 第一步：扫描
scanner = get_scanner()
scan_result = scanner.run_scan()
event_ids = scan_result["event_ids"]

# 第二步：提取
extractor = get_extractor()
extract_result = extractor.process_new_events(event_ids)
extracted_ids = extract_result["saved_ids"]

# 第三步：评分
scorer = get_risk_scorer()
score_result = scorer.score_batch_events(extracted_ids)
```

## 配置选项

### 最小配置（开发）
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
OPENAI_API_KEY=sk-...
DEBUG=True
```

### 完整配置（生产）
```bash
# LLM
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...

# 数据库
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...

# 邮件通知
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@esg-system.com

# 调度器
SCAN_INTERVAL_MINUTES=30

# 数据源 API
ALPHA_VANTAGE_KEY=...
NEWS_API_KEY=...
```

## 故障排除

### 问题 1：找不到数据库表

**原因**: Supabase 中的表还没有创建

**解决方案**:
1. 在 Supabase SQL 编辑器中运行 SCHEDULER_README.md 中的 SQL
2. 等待表创建完成
3. 重新运行程序

### 问题 2：LLM API 错误

**原因**: API Key 无效或配额用尽

**解决方案**:
1. 检查 .env 中的 API Key
2. 查看 LLM 使用配额
3. 程序会自动 fallback 到其他 LLM

### 问题 3：邮件发送失败

**原因**: SMTP 配置不正确

**解决方案**:
1. 验证 SMTP 主机和端口
2. 检查用户名和密码
3. 如果使用 Gmail，需要使用应用密码而不是账户密码

## 性能优化

### 批量处理优化
```python
# 不好：逐个处理
for event_id in events:
    scorer.score_event(event_id, data)

# 更好：批量处理
scorer.score_batch_events(event_ids)  # 内部优化
```

### 缓存使用
```python
# 检索器会自动缓存相同的问题
# 如果问题重复，会直接返回缓存结果
```

### 后台任务
```python
# 使用后台任务不阻塞 HTTP
background_tasks.add_task(long_running_function)

# 或使用 schedule 模块定期运行
orchestrator.schedule_periodic_scan_background(interval_minutes=30)
```

## 监控和日志

### 启用详细日志
```bash
export DEBUG=True
python -m gateway.main
```

### 查看执行统计
```python
orchestrator = get_orchestrator()
stats = orchestrator.get_pipeline_statistics(days=7)
print(f"成功率: {stats['success_rate']:.1f}%")
```

### 追踪特定事件
```python
# 查看事件的完整流程
event_id = "uuid-xxx"
matches = matcher.find_matching_users(event_data)
score = scorer.score_event(event_id, event_data)
notifications = notifier.send_notifications(event_id, matches)
```

## 下一步学习

1. **了解详情**
   - 阅读 [SCHEDULER_README.md](SCHEDULER_README.md) - 完整文档
   - 阅读 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - 实现细节

2. **运行测试**
   - `python test_scheduler.py --full` - 完整测试
   - `python demo_scheduler.py` - 功能演示

3. **自定义扩展**
   - 添加新的数据源（在 Scanner 中）
   - 自定义 LLM Prompts（在 prompts.py 中）
   - 添加新的通知渠道（在 Notifier 中）

4. **部署上线**
   - 配置 Supabase 数据库
   - 设置定期扫描任务
   - 配置邮件/Webhook 通知
   - 建立监控告警

## 获取帮助

### 调试技巧
```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查各个阶段的输出
result = orchestrator.run_full_pipeline()
import json
print(json.dumps(result, indent=2, default=str))
```

### 常见命令
```bash
# 运行演示
python demo_scheduler.py

# 运行测试
python test_scheduler.py --full

# 启动服务
python -m gateway.main

# 检查代码
pylint gateway/scheduler/

# 格式化代码
black gateway/scheduler/
```

## 一分钟总结

1. ✅ 安装依赖: `pip install -r requirements.txt`
2. ✅ 配置环境: 编辑 `.env`
3. ✅ 运行演示: `python demo_scheduler.py`
4. ✅ 启动服务: `python -m gateway.main`
5. ✅ 调用 API: `curl http://localhost:8000/scheduler/scan`

就这么简单！🚀

---

更多问题？查看 [SCHEDULER_README.md](SCHEDULER_README.md) 或 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
