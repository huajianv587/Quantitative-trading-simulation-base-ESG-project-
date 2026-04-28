# ESG Agentic RAG Copilot 交付部署与验收清单

这份文档用于产品交付、客户演示环境交接、实施上线前验收。

当前推荐交付基线：

- 应用模式：`APP_MODE=local`
- LLM 策略：`LLM_BACKEND_MODE=auto`
- 默认链路：`本地模型 -> DeepSeek -> OpenAI`
- 远端 GPU / 5090：不作为当前交付前置条件，只保留为后续可选增强方案

相关文档：

- 本地优先运行：`README.md`
- 本地混合/远端 GPU 可选方案：`docs/LOCAL_HYBRID_RUNBOOK_ZH.md`
- 远端 GPU 专项说明：`docs/REMOTE_GPU_RUNBOOK.md`
- Staging 检查：`docs/STAGING_RELEASE_RUNBOOK.md`

## 1. 交付物清单

交付前必须明确以下内容已经提供给客户或实施方：

- 源码仓库或打包产物
- `.env` 参数说明，不直接交付真实密钥
- 数据库迁移脚本：`gateway/db/migrations/001` 到 `004`
- 前端静态资源与后端启动方式
- 本地优先启动脚本：`scripts/run_local_first_windows.bat`
- 运行时诊断脚本：`scripts/runtime_doctor.py`
- Staging/验收脚本：`scripts/staging_check.py`
- 已知限制与后续增强项说明

## 2. 环境前置条件

基础环境：

- Python 3.11+，且项目 `.venv` 可正常创建
- Docker Desktop 或 Docker Engine
- Qdrant 可本地运行
- Supabase 项目已创建
- 至少配置一个云端兜底密钥：`DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`

推荐最小可用密钥：

- `SUPABASE_URL`
- `SUPABASE_API_KEY` 或 `SUPABASE_SERVICE_ROLE_KEY`
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`

可选项：

- `REMOTE_LLM_URL` / `REMOTE_LLM_API_KEY`
说明：仅在后续重新启用远端 GPU 时需要。

## 3. 部署模式选择

### 模式 A：本地优先交付基线

适用场景：

- 当前产品交付
- 演示环境
- 试运行环境
- 未接入 5090 / 远端 GPU 的阶段

关键配置：

```env
APP_MODE=local
LLM_BACKEND_MODE=auto
```

启动顺序：

1. `scripts\bootstrap_local_windows.bat`
2. `scripts\start_local_qdrant_windows.bat`
3. `scripts\run_local_first_windows.bat`

### 模式 B：本地应用 + 远端 GPU

适用场景：

- 后续恢复 5090 或远端算力
- 需要稳定的 LoRA 生成能力

关键配置：

```env
APP_MODE=hybrid
LLM_BACKEND_MODE=remote
REMOTE_LLM_URL=http://127.0.0.1:8010
REMOTE_LLM_API_KEY=...
```

说明：

- 该模式下生成链路为 `远端 GPU -> DeepSeek -> OpenAI`
- 不是当前交付必选项

## 4. 标准部署步骤

### 4.1 初始化环境

```bat
scripts\bootstrap_local_windows.bat
```

### 4.2 配置 `.env`

至少确认以下项：

```env
APP_MODE=local
LLM_BACKEND_MODE=auto
SUPABASE_URL=...
SUPABASE_API_KEY=...
DEEPSEEK_API_KEY=...
OPENAI_API_KEY=...
```

### 4.3 启动本地 Qdrant

```bat
scripts\start_local_qdrant_windows.bat
```

### 4.4 启动 API

```bat
scripts\run_local_first_windows.bat
```

### 4.5 运行体检

```bat
.venv\Scripts\python.exe scripts\runtime_doctor.py
```

验收预期：

- `local_api.ok = true`
- `qdrant.ok = true`
- `http://127.0.0.1:8012/health/ready` 返回 `200`

如果配置了远端 GPU，再额外检查：

- `remote_llm.ok = true`

## 5. 接口验收清单

### 5.1 健康检查

```bat
curl http://127.0.0.1:8012/health
```

必须满足：

- HTTP `200`
- `status = ok`
- 返回 `runtime`
- 返回 `modules`

建议核对：

- `runtime.llm_backend_mode = auto`
- `runtime.cloud_fallback_order = ["deepseek", "openai"]`

### 5.1.1 就绪检查

```bat
curl http://127.0.0.1:8012/health/ready
```

必须满足：

- HTTP `200`
- `ready = true`
- `modules.rag = true`

### 5.2 首页总览

```bat
curl http://127.0.0.1:8012/dashboard/overview
```

必须满足：

- HTTP `200`
- 返回 `spotlight`
- 返回 `metrics`
- 返回 `signals`

### 5.3 分析链路

```bat
.venv\Scripts\python.exe -c "import requests; r=requests.post('http://127.0.0.1:8012/agent/analyze', json={'session_id':'delivery-check','question':'请总结 Tesla 最近的 ESG 风险与机会'}, timeout=600); print(r.status_code); print(r.text)"
```

必须满足：

- HTTP `200`
- 返回 `answer`
- 返回 `confidence`
- 接口无 5xx

### 5.4 报告生成

```bat
.venv\Scripts\python.exe -c "import requests, json; r=requests.post('http://127.0.0.1:8012/admin/reports/generate', json={'report_type':'daily','companies':['Tesla'],'async':False}, timeout=600); print(r.status_code); print(r.text)"
```

必须满足：

- HTTP `200`
- 返回 `report_id`
- 返回 `status`

### 5.5 数据同步

```bat
.venv\Scripts\python.exe -c "import requests; r=requests.post('http://127.0.0.1:8012/admin/data-sources/sync', json={'companies':['Tesla'],'force_refresh':False}, timeout=300); print(r.status_code); print(r.text)"
```

必须满足：

- HTTP `200`
- 返回 `job_id`

## 6. 回归与质量门槛

交付前至少执行：

```bat
.venv\Scripts\python.exe -m pytest tests\test_api_contracts.py tests\test_llm_client_runtime.py -q
```

推荐执行：

```bat
.venv\Scripts\python.exe scripts\staging_check.py preflight
```

如果走 Docker / Staging：

```bat
.venv\Scripts\python.exe scripts\staging_check.py all --require-module rag --require-module esg_scorer
```

放行门槛：

- 关键测试通过
- `/health` 通过
- `/health/ready` 通过
- `/dashboard/overview` 通过
- `/agent/analyze` 真实问题通过
- `/admin/reports/generate` 通过

## 7. 安全与配置检查

交付前必须确认：

- `.env` 不进入版本库
- 演示环境不使用 `demo` 数据源密钥
- `CORS_ORIGINS` 不保留宽泛的生产配置
- 客户侧只拿到自己的真实密钥
- 日志中不输出明文密钥

## 8. 运维交接项

至少要交接清楚以下内容：

- 启动命令
- 停止命令
- 日志位置
- 故障排查入口
- 数据库迁移顺序
- 是否启用远端 GPU
- 当前 LLM 回退顺序
- 负责人和升级路径

建议附带：

- 一页架构图
- 一页环境变量说明
- 一页常见故障排查

## 9. 已知限制

当前版本交付时需明确说明：

- `gateway/main.py` 已拆分，但仍然共享单例运行时，适合单实例部署
- Dashboard 中部分内容在无实时数据时会进入 fallback 数据
- 远端 GPU 方案仍保留，但不是当前默认交付路径
- 历史文档 `docs/DEPLOYMENT_GUIDE.md` 不应作为唯一部署依据

## 10. 验收签字模板

建议在交付单中至少确认以下项目：

- 环境已成功启动
- 健康检查通过
- 首页总览通过
- 分析接口通过
- 报告接口通过
- 数据同步接口通过
- 配置与密钥已交接
- 运维联系人已确认

---

一句话版本：

**当前交付基线是本地优先运行，DeepSeek 为首选云端后备，OpenAI 为最终兜底；远端 GPU 保留为后续增强，不作为本次交付前置条件。**
