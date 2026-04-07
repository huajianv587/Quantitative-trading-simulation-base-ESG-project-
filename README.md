# ESG Agentic RAG Copilot

Enterprise ESG analysis and monitoring platform built with FastAPI, LangGraph, Qdrant, Supabase, and a local-first / cloud-fallback LLM runtime.

This README is intentionally bilingual:

- English first
- 中文 second

---

# English

## 1. Overview

ESG Agentic RAG Copilot is a product-oriented ESG intelligence system for:

- ESG question answering
- company-level ESG scoring
- retrieval-augmented report analysis
- proactive event monitoring
- scheduled report generation
- customer-facing dashboard delivery

It supports both reactive workflows, where a user asks a question, and proactive workflows, where the system scans, scores, and pushes ESG signals.

## 2. Current Delivery Baseline

This repository is currently prepared for product delivery with the following baseline:

- `APP_MODE=local`
- `LLM_BACKEND_MODE=auto`
- default LLM order: `Local -> DeepSeek -> OpenAI`
- remote GPU / 5090 is optional and not required for current delivery

Important behavior:

- If no local CUDA runtime is available, the local generation backend is skipped automatically.
- In CPU-only environments, the practical response path becomes `DeepSeek -> OpenAI`.
- Readiness is exposed through `GET /health/ready`.
- You should not send production traffic until `/health/ready` returns `200`.

## 3. What The Product Includes

- FastAPI backend with modular API routers
- LangGraph-based agent pipeline
- Qdrant-backed RAG retrieval
- Supabase-backed runtime data and reports
- ESG scoring and visualization utilities
- scheduler and reporting pipeline
- static frontend dashboard
- Windows local-first delivery scripts
- deployment, smoke-test, and runtime diagnostic scripts

## 4. Architecture

```text
Frontend (static SPA)
        |
        v
FastAPI Gateway
  |- /health
  |- /health/ready
  |- /agent/*
  |- /admin/*
  |- /dashboard/*
        |
        +--> Agentic RAG path
        |     |- Router Agent
        |     |- Retriever Agent
        |     |- Analyst Agent
        |     |- Verifier Agent
        |
        +--> Proactive scheduler path
              |- Scanner
              |- Event extractor
              |- Risk scorer
              |- Matcher
              |- Notifier
              |- Report generator

Shared runtime services
  |- Qdrant
  |- Supabase
  |- local / remote / cloud LLM client
```

## 5. Repository Layout

```text
.
|- gateway/
|  |- api/                 # FastAPI app factory, routers, API schemas
|  |- agents/              # LangGraph agents and ESG reasoning logic
|  |- rag/                 # RAG indexing, retrieval, embeddings, quality filters
|  |- scheduler/           # proactive monitoring and reporting pipeline
|  |- db/                  # Supabase runtime access
|  |- utils/               # LLM client, logging, cache, retry helpers
|  |- app_runtime.py       # shared runtime context
|  |- main.py              # thin application entry point
|  \- Dockerfile           # backend container image
|- frontend/               # static frontend app
|- scripts/                # bootstrap, smoke, doctor, build, delivery helpers
|- docs/                   # deployment and delivery documentation
|- tests/                  # automated tests
|- training/               # fine-tuning and evaluation utilities
|- docker-compose.yml      # local compose stack
|- requirements.txt
\- .env.example
```

## 6. Core Runtime Flow

### 6.1 Request flow

For a typical analysis request:

1. the API receives `/agent/analyze`
2. the router agent classifies the request
3. the retriever agent rewrites the query and fetches context
4. the analyst agent produces ESG analysis when needed
5. the verifier agent checks grounding and confidence
6. the API returns answer, confidence, and optional ESG scores

### 6.2 LLM fallback flow

Current behavior:

- `local` or `auto`: `Local -> DeepSeek -> OpenAI`
- `remote`: `Remote GPU -> DeepSeek -> OpenAI`
- `cloud`: `DeepSeek -> OpenAI`

## 7. Prerequisites

Minimum recommended environment:

- Python `3.11+`
- Docker Desktop or Docker Engine
- Qdrant available on port `6333`
- Supabase project and server-side key
- at least one cloud fallback key:
  - `DEEPSEEK_API_KEY`, or
  - `OPENAI_API_KEY`

Recommended for current delivery:

- Windows with the provided `.bat` scripts
- enough RAM for cold-start embedding warm-up

## 8. Minimal Environment Variables

Start from `.env.example` and at minimum configure:

```env
APP_MODE=local
LLM_BACKEND_MODE=auto

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=...

DEEPSEEK_API_KEY=...
OPENAI_API_KEY=...
```

Optional only when you explicitly use remote GPU mode:

```env
REMOTE_LLM_URL=http://127.0.0.1:8010
REMOTE_LLM_API_KEY=...
```

## 9. Quick Start

### 9.1 Windows local-first startup

This is the recommended product delivery path.

```bat
scripts\bootstrap_local_windows.bat
scripts\start_local_qdrant_windows.bat
scripts\run_local_first_windows.bat
```

Then wait for readiness:

```bat
curl http://127.0.0.1:8000/health/ready
```

When it returns `200`, open:

- app: `http://127.0.0.1:8000/app`
- API docs: `http://127.0.0.1:8000/docs`

### 9.2 Docker Compose

```bash
docker compose up -d qdrant
docker compose up -d
```

Check readiness:

```bash
curl http://127.0.0.1:8000/health/ready
```

### 9.3 Static frontend build

```bash
npm run build:static
```

This writes the static bundle to `dist/`.

## 10. Health And Readiness

### `GET /health`

Use this for liveness and general runtime inspection.

It returns:

- runtime mode
- backend fallback order
- module flags
- general service status

### `GET /health/ready`

Use this for production readiness.

It returns `200` only when the required runtime modules are ready, including:

- RAG
- ESG scorer
- report scheduler

If readiness is not complete yet, it returns `503`.

## 11. Cold Start And Warm-Up Notes

This project has a real warm-up phase on cold start.

Typical reasons:

- loading the persisted Qdrant-backed index
- restoring large docstore metadata
- loading the local embedding model
- starting the reporting scheduler

Operational guidance:

- start the service first
- wait until `/health/ready` returns `200`
- only then attach traffic through Nginx / domain / reverse proxy

If you skip this, the first real request may wait several minutes.

## 12. Common Commands

### Full test suite

```bash
python -m pytest -q
```

### Runtime doctor

```bash
python scripts/runtime_doctor.py
```

### Local smoke test

```bash
python scripts/local_api_smoke.py --app-mode local --llm-backend-mode auto
```

### Staging preflight

```bash
python scripts/staging_check.py preflight
```

### Generate the customer delivery document

```bash
python scripts/generate_customer_delivery_doc.py
```

Output:

- `dist/ESG_Agentic_RAG_Copilot_客户交付说明_2026-04-07.docx`

## 13. Key Scripts

### Delivery / runtime

- `scripts/bootstrap_local_windows.bat`
- `scripts/start_local_qdrant_windows.bat`
- `scripts/run_local_first_windows.bat`
- `scripts/run_local_hybrid_windows.bat`
- `scripts/local_api_smoke.py`
- `scripts/runtime_doctor.py`
- `scripts/staging_check.py`

### RAG / maintenance

- `scripts/rebuild_rag_index.py`
- `scripts/rag_quality_check.py`

### Delivery docs

- `scripts/generate_customer_delivery_doc.py`

## 14. API Highlights

Main product endpoints:

- `POST /agent/analyze`
- `POST /agent/esg-score`
- `GET /dashboard/overview`
- `POST /admin/reports/generate`
- `POST /admin/data-sources/sync`
- `GET /health`
- `GET /health/ready`

See:

- [docs/API_ENDPOINTS.md](docs/API_ENDPOINTS.md)

## 15. Product Delivery Docs

Use these documents during handoff and deployment:

- [docs/PRODUCT_DELIVERY_CHECKLIST_ZH.md](docs/PRODUCT_DELIVERY_CHECKLIST_ZH.md)
- [docs/STAGING_RELEASE_RUNBOOK.md](docs/STAGING_RELEASE_RUNBOOK.md)
- [docs/LOCAL_HYBRID_RUNBOOK.md](docs/LOCAL_HYBRID_RUNBOOK.md)
- [docs/LOCAL_HYBRID_RUNBOOK_ZH.md](docs/LOCAL_HYBRID_RUNBOOK_ZH.md)
- [docs/REMOTE_GPU_RUNBOOK.md](docs/REMOTE_GPU_RUNBOOK.md)
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)

## 16. Troubleshooting

### Qdrant is running in Docker Desktop, but the app still cannot connect

Make sure you are using the compose-managed Qdrant with port mapping:

- expected host port: `6333`
- expected active container: `esg-qdrant`

The helper script `scripts/start_local_qdrant_windows.bat` will stop a standalone container named `qdrant` if it is blocking port `6333`.

### `/health` is OK but `/health/ready` is still `503`

This usually means one or more runtime modules are still warming up.

Wait longer and check:

- Qdrant connectivity
- local embedding model warm-up
- docstore restore

### Local model never runs

That is expected on CPU-only hosts.

In that case the runtime falls back to:

- `DeepSeek -> OpenAI`

### First analysis request is slow

That usually means:

- the service was queried before readiness completed, or
- the embedding model was loaded for the first time

## 17. Security Notes

- never commit your real `.env`
- keep server-side Supabase keys out of frontend delivery
- restrict `CORS_ORIGINS` in production
- rotate API keys regularly

## 18. License

MIT

---

# 中文

## 1. 项目简介

ESG Agentic RAG Copilot 是一个面向产品交付的 ESG 智能分析平台，覆盖：

- ESG 问答分析
- 公司级 ESG 评分
- 基于检索增强的报告理解
- 主动式事件监测
- 定时报表生成
- 面向客户交付的看板与接口

它既支持用户主动提问，也支持系统主动扫描、评分、推送和出报告。

## 2. 当前交付基线

当前仓库已经按产品交付口径整理为以下默认基线：

- `APP_MODE=local`
- `LLM_BACKEND_MODE=auto`
- 默认大模型顺序：`本地模型 -> DeepSeek -> OpenAI`
- 远端 GPU / 5090 不是本次交付前置条件，只保留为后续增强方案

需要特别注意：

- 如果本机没有 CUDA，本地生成后端会自动跳过。
- 在纯 CPU 环境下，实际回答链路通常会变成 `DeepSeek -> OpenAI`。
- 生产就绪检查使用 `GET /health/ready`。
- 正式接流量之前，必须等 `/health/ready` 返回 `200`。

## 3. 产品能力范围

- 基于 FastAPI 的后端 API
- 基于 LangGraph 的 Agent 推理链路
- 基于 Qdrant 的 RAG 检索
- 基于 Supabase 的运行时数据与报表存储
- ESG 评分与可视化能力
- 主动扫描与报表调度能力
- 静态前端看板
- 面向 Windows 的本地优先交付脚本
- 部署、烟测、体检和交付辅助脚本

## 4. 系统架构

```text
静态前端 SPA
     |
     v
FastAPI Gateway
  |- /health
  |- /health/ready
  |- /agent/*
  |- /admin/*
  |- /dashboard/*
     |
     +--> Agentic RAG 分析链路
     |     |- Router Agent
     |     |- Retriever Agent
     |     |- Analyst Agent
     |     \- Verifier Agent
     |
     \--> 主动调度链路
           |- Scanner
           |- Event extractor
           |- Risk scorer
           |- Matcher
           |- Notifier
           \- Report generator

共享运行时能力
  |- Qdrant
  |- Supabase
  \- 本地 / 远端 / 云端 LLM 客户端
```

## 5. 仓库结构

```text
.
|- gateway/
|  |- api/                 # FastAPI 工厂、路由、接口 schema
|  |- agents/              # LangGraph Agent 与 ESG 推理逻辑
|  |- rag/                 # RAG 索引、检索、embedding、质量过滤
|  |- scheduler/           # 主动监控与报表调度
|  |- db/                  # Supabase 运行时访问
|  |- utils/               # LLM、日志、缓存、重试等通用工具
|  |- app_runtime.py       # 共享运行时上下文
|  |- main.py              # 轻量主入口
|  \- Dockerfile           # 后端镜像
|- frontend/               # 静态前端
|- scripts/                # 初始化、烟测、体检、构建、交付脚本
|- docs/                   # 部署与交付文档
|- tests/                  # 自动化测试
|- training/               # 微调与评估工具
|- docker-compose.yml      # 本地 compose 编排
|- requirements.txt
\- .env.example
```

## 6. 运行链路说明

### 6.1 分析请求链路

一次典型的 `/agent/analyze` 请求会经过：

1. API 接收问题
2. Router Agent 做问题分类
3. Retriever Agent 改写查询并检索上下文
4. 需要时由 Analyst Agent 产出 ESG 分析
5. Verifier Agent 做 grounded / confidence 校验
6. 返回答案、置信度和可选 ESG 评分

### 6.2 LLM 回退链路

当前行为如下：

- `local` 或 `auto`：`本地 -> DeepSeek -> OpenAI`
- `remote`：`远端 GPU -> DeepSeek -> OpenAI`
- `cloud`：`DeepSeek -> OpenAI`

## 7. 环境前置要求

建议最小环境：

- Python `3.11+`
- Docker Desktop 或 Docker Engine
- `6333` 端口可访问的 Qdrant
- 已创建的 Supabase 项目
- 至少一个云端兜底密钥：
  - `DEEPSEEK_API_KEY`
  - 或 `OPENAI_API_KEY`

当前交付最推荐：

- Windows 环境
- 使用仓库内 `.bat` 启动脚本
- 具备足够内存用于冷启动预热

## 8. 最小环境变量

从 `.env.example` 复制后，至少配置以下项：

```env
APP_MODE=local
LLM_BACKEND_MODE=auto

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=...

DEEPSEEK_API_KEY=...
OPENAI_API_KEY=...
```

只有在你明确启用远端 GPU 模式时，才需要：

```env
REMOTE_LLM_URL=http://127.0.0.1:8010
REMOTE_LLM_API_KEY=...
```

## 9. 快速开始

### 9.1 Windows 本地优先启动

这是当前产品交付的推荐路径。

```bat
scripts\bootstrap_local_windows.bat
scripts\start_local_qdrant_windows.bat
scripts\run_local_first_windows.bat
```

然后等待就绪：

```bat
curl http://127.0.0.1:8000/health/ready
```

当它返回 `200` 后，访问：

- 应用页面：`http://127.0.0.1:8000/app`
- API 文档：`http://127.0.0.1:8000/docs`

### 9.2 Docker Compose 启动

```bash
docker compose up -d qdrant
docker compose up -d
```

检查就绪状态：

```bash
curl http://127.0.0.1:8000/health/ready
```

### 9.3 静态前端构建

```bash
npm run build:static
```

构建产物会输出到 `dist/`。

## 10. 健康检查与就绪检查

### `GET /health`

用于存活检查和运行时状态查看。

返回内容包括：

- 当前运行模式
- LLM 回退顺序
- 模块状态
- 基本服务信息

### `GET /health/ready`

用于生产环境就绪探针。

只有在关键模块都准备完成后才会返回 `200`，包括：

- RAG
- ESG scorer
- report scheduler

如果还没准备好，会返回 `503`。

## 11. 冷启动与预热说明

这个项目在冷启动时确实存在预热阶段。

主要耗时来自：

- 从 Qdrant 恢复索引
- 恢复本地 docstore 元数据
- 首次加载本地 embedding 模型
- 启动报表调度器

上线建议：

- 先启动服务
- 等 `/health/ready` 返回 `200`
- 再通过 Nginx / 域名 / 反向代理接入流量

如果跳过这一步，首个真实请求可能要等待数分钟。

## 12. 常用命令

### 全量测试

```bash
python -m pytest -q
```

### 运行时体检

```bash
python scripts/runtime_doctor.py
```

### 本地烟测

```bash
python scripts/local_api_smoke.py --app-mode local --llm-backend-mode auto
```

### Staging 预检

```bash
python scripts/staging_check.py preflight
```

### 生成客户交付 Word

```bash
python scripts/generate_customer_delivery_doc.py
```

输出位置：

- `dist/ESG_Agentic_RAG_Copilot_客户交付说明_2026-04-07.docx`

## 13. 关键脚本

### 交付与运行

- `scripts/bootstrap_local_windows.bat`
- `scripts/start_local_qdrant_windows.bat`
- `scripts/run_local_first_windows.bat`
- `scripts/run_local_hybrid_windows.bat`
- `scripts/local_api_smoke.py`
- `scripts/runtime_doctor.py`
- `scripts/staging_check.py`

### RAG 与维护

- `scripts/rebuild_rag_index.py`
- `scripts/rag_quality_check.py`

### 交付文档辅助

- `scripts/generate_customer_delivery_doc.py`

## 14. 主要接口

产品最常用的接口包括：

- `POST /agent/analyze`
- `POST /agent/esg-score`
- `GET /dashboard/overview`
- `POST /admin/reports/generate`
- `POST /admin/data-sources/sync`
- `GET /health`
- `GET /health/ready`

完整接口说明见：

- [docs/API_ENDPOINTS.md](docs/API_ENDPOINTS.md)

## 15. 交付与部署文档

交付、部署和验收时建议优先查看：

- [docs/PRODUCT_DELIVERY_CHECKLIST_ZH.md](docs/PRODUCT_DELIVERY_CHECKLIST_ZH.md)
- [docs/STAGING_RELEASE_RUNBOOK.md](docs/STAGING_RELEASE_RUNBOOK.md)
- [docs/LOCAL_HYBRID_RUNBOOK.md](docs/LOCAL_HYBRID_RUNBOOK.md)
- [docs/LOCAL_HYBRID_RUNBOOK_ZH.md](docs/LOCAL_HYBRID_RUNBOOK_ZH.md)
- [docs/REMOTE_GPU_RUNBOOK.md](docs/REMOTE_GPU_RUNBOOK.md)
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)

## 16. 常见问题

### Docker Desktop 里看到 Qdrant 在跑，但项目还是连不上

请确认你使用的是带宿主机端口映射的 compose 管理版 Qdrant：

- 预期端口：`6333`
- 预期容器：`esg-qdrant`

`scripts/start_local_qdrant_windows.bat` 会自动停掉一个名为 `qdrant` 的独立旧容器，以释放 `6333` 端口。

### `/health` 正常，但 `/health/ready` 还是 `503`

这通常说明运行时还在预热。

继续等待，并检查：

- Qdrant 是否可连通
- 本地 embedding 模型是否已热起来
- docstore 是否恢复完成

### 本地模型一直没有执行

如果当前主机没有 CUDA，这属于预期行为。

这时回答链路会回退到：

- `DeepSeek -> OpenAI`

### 第一个分析请求很慢

通常意味着：

- 服务在 ready 前就被打进了真实请求
- 或 embedding 模型第一次被加载

## 17. 安全说明

- 不要把真实 `.env` 提交到仓库
- 不要把服务端 Supabase 密钥暴露到前端
- 生产环境要收紧 `CORS_ORIGINS`
- API 密钥建议定期轮换

## 18. License

MIT
