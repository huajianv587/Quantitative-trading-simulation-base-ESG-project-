# ESG 量化智能交易系统

ESG 量化智能交易系统是一个生产级 ESG 量化平台，融合了以下核心能力：

- ESG 检索增强生成（RAG）与多智能体推理
- 因子研究与投资组合构建
- 回测引擎与模拟盘执行规划
- Supabase 元数据存储与 Cloudflare R2 制品存储
- 产品官网（`/`）与控制台（`/app`）

---

## 目录

- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [仓库结构](#仓库结构)
- [技术栈](#技术栈)
- [API 接口](#api-接口)
- [存储方案](#存储方案)
- [测试](#测试)
- [注意事项](#注意事项)

---

## 系统架构

本系统采用双层架构并行运行：

1. **当前运行实现层**：位于 `gateway/`、`frontend/`、`training/`、`scripts/` 目录下，是当前正在运行的生产服务。
2. **蓝图标准化架构层**：顶层目录按工业级标准布局，与目标架构 `esg-quant-intelligence/` 对齐，包含兼容适配器。

整体数据流如下：

```
市场数据采集 → 信号生成 → ML 预测（P1 模型组）
→ 投资组合构建（P2 决策栈） → 执行规划
→ 模拟盘交易（Alpaca）→ 报告生成 → 智能体推理
```

---

## 核心功能

### 1. 量化研究流水线（P0–P2）

| 阶段 | 名称 | 功能 |
|------|------|------|
| P0 | Alpha 排名器 | 信号生成与验证 |
| P1 | 模型组 | 收益预测、波动率预测、市场机制分类 |
| P2 | 决策栈 | 策略选择与执行决策 |

### 2. 多智能体研究系统

- 基于 **LangGraph** 编排的自主研究智能体
- ESG 事件提取与分析智能体
- 风险评估、策略制定、宏观分析等专项智能体
- 向量记忆、关系记忆、决策溯源等记忆系统

### 3. ESG 感知型投资组合构建

- ESG 评分框架（E/S/G 三维度评分）
- ESG Delta 分析（相对行业的 ESG 改善量）
- 多因子投资组合优化
- 因子中性化技术

### 4. 回测与前向验证

- Monte Carlo 模拟
- 交易成本建模
- 反事实分析
- 绩效归因（Sharpe、最大回撤、CVaR）
- 前向滚动交叉验证

### 5. 模拟盘交易与执行

- Alpaca 模拟盘集成
- 多券商支持（Alpaca、老虎证券、长桥证券、IBKR）
- 订单全生命周期管理
- 风险控制与熔断机制

### 6. 因子分析

- **Alpha158** 量化因子库（158 个 Alpha 因子）
- 19 种以上技术指标（趋势、振荡器、成交量等）
- **另类数据信号**：
  - 卫星热成像（工厂活跃度）
  - 车辆计数（停车场/工厂）
  - 港口船只检测（贸易量）
  - 植被指数（NDVI，农业/环境）
  - 供应链网络分析
- IC/ICIR 分析
- PCA 降维
- 自动因子挖掘

### 7. 基本面与事件分析

- 盈利质量评估
- 估值倍数分析
- 增长指标分析
- 基于 LLM 的财报解析
- CEO 演讲情绪分析
- 企业事件日历

### 8. RAG 智能 ESG 知识库

- ESG 报告文档检索（Qdrant 向量数据库）
- LlamaIndex 查询引擎
- BM25 关键字检索
- 多轮对话历史管理

### 9. 自动化报告

- 投资组合绩效 Tearsheet
- 因子归因报告
- 风险监控仪表盘
- 基准比较
- 定时报告生成与推送

### 10. Web 控制台

- 实时 K 线图（含技术指标叠加）
- 信号摘要与 AI 生成分析
- 实时持仓与盈亏追踪
- 系统状态监控（各架构层健康状态）
- 市场板块热力图
- ESG 评分展示
- 回测操作界面
- 研究工作台与模型管理
- 支持中英文双语切换

### 11. 风险管理

- 因子敞口限制
- Sharpe 比率实时监控
- 条件风险价值（CVaR）
- 最大回撤控制
- 压力测试场景模拟
- 合规检查
- 模型风险管理

### 12. 模型训练与优化

- LoRA 微调（ESG 领域专用）
- Optuna 超参数优化
- 强化学习（PPO）策略训练
- 因果推断模型（DoWhy、LiNGAM、Granger）
- XGBoost / LightGBM 集成模型

---

## 快速开始

### 前置依赖

```bash
pip install -r requirements.txt
```

### 环境配置

复制示例配置文件并填写必要的密钥：

```bash
cp .env.example .env
# 编辑 .env，填入 Supabase、Cloudflare R2、Alpaca、OpenAI 等凭据
```

### 启动服务

```bash
python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000
```

启动后访问：

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8000/` | 产品官网 |
| `http://127.0.0.1:8000/app` | 控制台 |
| `http://127.0.0.1:8000/docs` | API 文档（Swagger UI） |
| `http://127.0.0.1:8000/api/v1/quant/platform/overview` | 量化平台概览 |

### Docker 启动（含 Qdrant 向量数据库）

```bash
docker-compose up -d
```

---

## 仓库结构

```
.
├── gateway/                  # 主 FastAPI 服务（生产运行层）
│   ├── main.py               # 应用入口
│   ├── api/                  # API 路由（quant、agent、reports、scheduler、auth）
│   ├── quant/                # 量化核心服务（P1/P2 模型、市场数据、执行）
│   ├── scheduler/            # 后台调度（报告、事件分类、数据采集）
│   ├── db/                   # 数据库客户端（Supabase）
│   └── utils/                # 工具模块（日志、缓存、LLM 客户端、重试）
│
├── agents/                   # 多智能体系统（LangGraph）
│   ├── graph/                # 工作流编排（state、edges、workflow）
│   ├── memory/               # 智能体记忆（向量、关系、决策追踪）
│   └── *_agent.py            # 各类专项智能体
│
├── models/                   # 机器学习模型
│   ├── supervised/           # 监督学习（XGBoost、LightGBM、集成模型）
│   ├── lora/                 # LoRA 微调
│   ├── causal/               # 因果推断
│   └── reinforcement/        # 强化学习（PPO）
│
├── analysis/                 # 因子与技术分析
│   ├── technical/            # 技术指标
│   ├── factors/              # 因子研究（Alpha158、IC/ICIR、PCA）
│   ├── fundamental/          # 基本面分析
│   └── alternative/          # 另类数据（卫星、港口、供应链）
│
├── backtest/                 # 回测引擎
│   ├── backtest_engine.py    # 核心回测框架
│   ├── walk_forward.py       # 前向滚动验证
│   ├── monte_carlo.py        # Monte Carlo 模拟
│   └── performance_attribution.py  # 绩效归因
│
├── risk/                     # 风险管理
│   ├── cvar_risk.py          # CVaR
│   ├── drawdown_controller.py # 最大回撤控制
│   └── stress_testing.py     # 压力测试
│
├── rag/                      # 检索增强生成
│   ├── esg_retriever.py      # ESG 文档检索
│   ├── qdrant_store.py       # Qdrant 向量库
│   └── llama_index_pipeline.py # LlamaIndex 流水线
│
├── reporting/                # 报告生成
│   ├── report_generator.py   # 主报告构建器
│   ├── tearsheet.py          # 绩效 Tearsheet
│   └── dashboard/            # 仪表盘（投资组合、风险、因子热力图）
│
├── training/                 # 模型训练脚本（31 个）
│
├── frontend/                 # Web 前端（原生 JS）
│   ├── js/pages/             # 页面模块（控制台、回测、组合、研究等）
│   └── js/modules/           # 共享模块（技术指标、多语言、API）
│
├── data/                     # 数据管理（采集、治理、RAG 训练数据）
├── database/                 # 数据库 Schema 与迁移
├── api/                      # 标准化 API 层（Pydantic Schema）
├── config/                   # 配置文件（settings、api_keys、logging）
├── notebooks/                # Jupyter Notebook 演示（6 个）
├── tests/                    # 测试套件（35+ 测试文件）
├── e2e/                      # 端到端测试（Playwright）
├── deploy/                   # 部署配置（Docker、云部署模板）
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 技术栈

### 后端

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.104.1 + Uvicorn |
| LLM | OpenAI、Anthropic Claude |
| 智能体框架 | LangChain、LangGraph |
| RAG | LlamaIndex 0.10.58、Qdrant、BM25 |
| 机器学习 | PyTorch 2.1.1、Scikit-learn、XGBoost 2.0、LightGBM |
| 微调 | PEFT（LoRA）、Transformers、Sentence-Transformers |
| 数据库 | Supabase（PostgreSQL）、Psycopg2 |
| 量化数据 | yfinance、Alpaca API |
| 券商集成 | Alpaca、老虎证券、长桥证券、IBKR |
| 存储 | Cloudflare R2、Supabase、本地备用存储 |
| 可视化 | Plotly |
| 数据模型 | Pydantic 2.8+ |

### 前端

| 类别 | 技术 |
|------|------|
| 语言 | 原生 JavaScript（ES6+） |
| 测试 | Playwright（E2E） |
| 多语言 | 中英文双语支持 |

### 基础设施

| 类别 | 技术 |
|------|------|
| 容器化 | Docker & Docker Compose |
| 向量数据库 | Qdrant |
| 制品存储 | Cloudflare R2 |
| 元数据存储 | Supabase |

---

## API 接口

### 量化平台

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/quant/platform/overview` | 系统状态概览 |
| GET | `/api/v1/quant/universe/default` | 默认股票池 |
| POST | `/api/v1/quant/research/run` | 运行研究流水线 |
| POST | `/api/v1/quant/portfolio/optimize` | 投资组合优化 |
| POST | `/api/v1/quant/p1/stack/run` | 执行 P1 模型 |
| POST | `/api/v1/quant/p2/decision/run` | 执行 P2 决策 |
| POST | `/api/v1/quant/backtest/run` | 运行回测 |
| POST | `/api/v1/quant/execution/plan` | 生成执行计划 |

### 智能体 / RAG

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/agent/query` | 查询 ESG 文档 |
| POST | `/agent/session` | 创建对话会话 |
| POST | `/agent/analyze` | ESG 分析 |
| POST | `/agent/esg-score` | ESG 评分 |

### 报告

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/reports/generate` | 生成报告 |
| GET | `/api/v1/reports/list` | 查看报告列表 |
| POST | `/api/v1/reports/schedule` | 定时报告配置 |

完整接口文档请访问 `/docs`（Swagger UI）。

---

## 存储方案

| 类型 | 方案 | 用途 |
|------|------|------|
| 结构化元数据 | Supabase（PostgreSQL） | 用户数据、任务记录、信号历史 |
| 制品存储 | Cloudflare R2 | 模型文件、报告、训练数据 |
| 向量检索 | Qdrant | ESG 文档嵌入向量 |
| 本地备用 | `storage/quant/` | 云服务不可用时的降级方案 |

---

## 测试

### 运行核心测试套件

```bash
python -m pytest tests/test_api_contracts.py tests/test_quant_api.py \
  tests/test_site_delivery.py tests/test_frontend_click_contracts.py -q
```

### 运行全量测试

```bash
python -m pytest tests/ -q
```

### 运行端到端测试（需启动服务）

```bash
npx playwright test
```

测试套件覆盖范围（35+ 测试文件）：

- API 契约验证
- 量化服务（P1/P2 流水线）
- 回测引擎
- RAG 系统
- 多智能体系统
- 数据采集、风险管理、因子分析
- 前端交互

---

## 注意事项

- **降级处理**：若 Supabase 或 Cloudflare R2 凭据缺失，系统自动降级为本地存储，不影响核心功能运行。
- **模型训练**：量化训练栈设计支持扩展至远程 GPU（如 RTX 5090）进行微调与训练。
- **架构蓝图**：顶层蓝图目录是与目标工业化架构对齐的标准化脚手架，同时复用当前已运行的实现。
- **模拟盘模式**：所有交易执行默认使用模拟盘（Paper Trading），生产交易需额外配置并经过严格风险审查。
- **多语言支持**：前端控制台支持中英文切换，适合国内外团队协作使用。

---

## Jupyter Notebook 演示

| 文件 | 内容 |
|------|------|
| `notebooks/01_data_exploration.ipynb` | 市场数据探索 |
| `notebooks/02_factor_analysis.ipynb` | 因子研究与 IC 分析 |
| `notebooks/03_backtest_demo.ipynb` | 回测示例 |
| `notebooks/04_satellite_signal.ipynb` | 卫星另类数据信号 |
| `notebooks/05_agent_workflow.ipynb` | 多智能体工作流演示 |
| `notebooks/06_sci_paper_data.ipynb` | 学术论文数据研究 |
