# 5090 云端部署说明

## 目标

这套部署面向以下目标：

- 使用你自己训练好的 `Qwen ESG LoRA`
- 同时启用 `alpha_ranker`、`p1_suite`、`sequence_forecaster`、`event_classifier`、`p2_selector`、`contextual_bandit`
- 在单台 `RTX 5090 32GB` 上形成完整的研究、执行、RAG、监控闭环

## 部署组件

当前推荐在同一台 5090 机器上部署这 4 个服务：

1. `remote-llm`
   - 使用 `Qwen/Qwen2.5-7B-Instruct + ESG LoRA`
   - 代码入口：`model-serving/remote_llm_server.py`
2. `api`
   - FastAPI 主服务
   - 直接加载所有量化模型 checkpoint
3. `quant-scheduler`
   - 开盘前信号计算
   - paper execution
   - journal sync
4. `qdrant`
   - 向量检索

## 运行时模型映射

- `model-serving/checkpoint/`：`Qwen ESG LoRA`
- `model-serving/checkpoint/alpha_ranker/`：Alpha ranker
- `model-serving/checkpoint/p1_suite/`：P1 tabular suite
- `model-serving/checkpoint/sequence_forecaster/`：多目标序列模型
- `model-serving/checkpoint/event_classifier/controversy_label/`：事件分类器
- `model-serving/checkpoint/p2_selector/`：P2 selector
- `model-serving/checkpoint/contextual_bandit/`：bandit policy
- `model-serving/checkpoint/gnn_graph/`：GNN graph refiner（可选）

## 部署前准备

云端机器至少准备：

- Docker
- Docker Compose
- NVIDIA Driver
- NVIDIA Container Toolkit
- 项目根目录代码
- `.env`
- 最新 `model-serving/checkpoint/`
- 最新 `data/`

建议确认：

- `LLM_BACKEND_MODE=remote`
- `REMOTE_LLM_BASE_MODEL=Qwen/Qwen2.5-7B-Instruct`
- `REMOTE_LLM_ADAPTER_PATH=model-serving/checkpoint`
- `P1_SEQUENCE_ENABLED=true`
- `EVENT_CLASSIFIER_ENABLED=true`
- `P2_BANDIT_ENABLED=true`
- `P2_REGIME_MIXTURE_ENABLED=true`
- `AUTH_DEFAULT_REQUIRED=true`

## 一键部署

在服务器项目根目录执行：

```bash
bash scripts/deploy_5090.sh
```

脚本会做这些事：

1. 校验 `.env`
2. 启动 `docker-compose.5090.yml`
3. 运行 `scripts/healthcheck_5090.py`
4. 将健康检查结果写入 `storage/quant/deploy_5090_health.json`

## 手动部署

如果你想手动执行：

```bash
docker compose -f docker-compose.5090.yml up -d --build
python scripts/healthcheck_5090.py --retries 20 --retry-delay 10
```

## 自动恢复

当服务异常时执行：

```bash
bash scripts/autorecover_5090.sh
```

它会：

1. 运行一次健康检查
2. 找出不健康的服务
3. 只重启对应服务
4. 再次运行健康检查确认恢复

健康检查输出会写到：

```text
storage/quant/autorecover_5090_health.json
```

## 验收命令

### 基础健康

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/ready
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:6333/healthz
```

### 项目级验收

```bash
python scripts/runtime_doctor.py
python scripts/healthcheck_5090.py --retries 3 --retry-delay 5
python scripts/full_system_smoke.py --host 127.0.0.1 --port 8000 --startup-timeout 120 --request-timeout 180
```

### 查看日志

```bash
docker compose -f docker-compose.5090.yml ps
docker compose -f docker-compose.5090.yml logs -f api
docker compose -f docker-compose.5090.yml logs -f remote-llm
docker compose -f docker-compose.5090.yml logs -f quant-scheduler
```

## 4080 和 5090 的取舍

- 如果只是运行 `Qwen LoRA` 单服务，`RTX 4080 16GB` 可以尝试
- 如果要同机承载：
  - `remote-llm`
  - `api`
  - `quant-scheduler`
  - `qdrant`
  - 所有量化 checkpoint
  那么 `RTX 5090 32GB` 更稳

## 当前边界

当前代码已经把这些模型接入主业务流：

- `Qwen ESG LoRA`
- `alpha_ranker`
- `p1_suite`
- `sequence_forecaster`
- `event_classifier`
- `p2_selector`
- `contextual_bandit`

如果 `gnn_graph` checkpoint 也准备好了，系统会优先用 GNN graph refiner；否则自动回退到启发式 graph runtime。

也就是说，剩下主要是：

- 云端常驻部署
- `.env` 中真实 key
- 你后续继续训练更强版本的模型权重
