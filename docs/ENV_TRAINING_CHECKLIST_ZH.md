# ESG Quant 环境变量与训练清单

本文档列出当前仓库为了跑到“产品级闭环”最关键的外部配置项，以及仍然需要人工训练/部署的模型任务。

## 1. 本地可直接运行，不填也能工作

这些项在当前版本里都支持回退模式：

- `APP_MODE`
- `LLM_BACKEND_MODE`
- `QUANT_DEFAULT_CAPITAL`
- `QUANT_DEFAULT_BENCHMARK`
- `QUANT_DEFAULT_UNIVERSE`
- `CORS_ORIGINS`
- `QDRANT_URL`
- `EMBEDDING_PROVIDER`
- `LOCAL_EMBEDDING_MODEL`
- `REMOTE_TRAINING_TARGET`

## 2. 你需要补进 `.env` 的关键项

### 2.1 云数据库与工件存储

用于真正的产品化元数据沉淀、报告落库和工件留存：

- `SUPABASE_URL`
- `SUPABASE_API_KEY` 或 `SUPABASE_SERVICE_ROLE_KEY`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`
- `R2_ENDPOINT`
- `R2_PUBLIC_BASE_URL`

### 2.2 外部数据源

用于把演示数据切换成真实行情、新闻、事件和 ESG 采集：

- `ALPHA_VANTAGE_API_KEY`
- `NEWSAPI_KEY`
- `FINNHUB_API_KEY`
- `SEC_EDGAR_EMAIL`
- `HYFINNAN_API_KEY`
- `RAPIDAPI_KEY`
- `RAPIDAPI_HOST`

### 2.3 邮件与通知

用于推送规则、订阅通知和报告下发：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `EMAIL_FROM`

### 2.4 远端 LLM / 推理服务

用于把当前本地回退推理切换到正式服务：

- `REMOTE_LLM_URL`
- `REMOTE_LLM_API_KEY`
- `REMOTE_LLM_BASE_MODEL`
- `REMOTE_LLM_ADAPTER_PATH`
- `REMOTE_LLM_HOST`
- `REMOTE_LLM_PORT`
- `REMOTE_LLM_ALLOW_CPU`

## 3. 需要你人工训练或继续微调的模型

以下任务已经有代码入口，但仍需要你提供算力和正式训练：

### 3.1 ESG LoRA 继续训练

目标：

- 在现有 `Qwen/Qwen2.5-7B-Instruct` 基础上继续做 ESG 领域 LoRA。
- 把 SEC、ESG 报告、报告问答、研究摘要、事件解释继续灌进领域数据。

代码入口：

- `training/finetune.py`
- `scripts/train_lora.py`
- `training/evaluate_model.py`

建议你准备：

- 更高质量的 `train.jsonl` / `val.jsonl`
- 企业 ESG 报告问答对
- 财报解析问答对
- 多因子研究结论到自然语言报告的样本

### 3.2 远端推理服务部署

目标：

- 把微调后的 LoRA 或合并权重挂到远端推理服务，供 `/agent/*` 与报告生成使用。

代码入口：

- `model-serving/remote_llm_server.py`

### 3.3 强化量化预测模型

目标：

- 用真实历史特征做监督学习收益预测与权重打分，而不是当前演示/回退逻辑。

代码入口：

- `models/supervised/xgb_lgb_scorer.py`
- `models/deep_learning/lstm_predictor.py`
- `models/deep_learning/patch_tst.py`
- `models/deep_learning/tft_model.py`

### 3.4 RL 策略 Agent

目标：

- 把仓位控制和多期再平衡接入真正训练好的 RL 策略，而不是仅保留骨架。

代码入口：

- `models/reinforcement/ppo_agent.py`
- `models/reinforcement/sac_agent.py`
- `models/reinforcement/trademaster_adapter.py`

## 4. 当前建议的落地顺序

1. 先补 `SUPABASE_*` 和 `R2_*`，让研究/回测/执行工件真正落库。
2. 再补 `NEWSAPI_KEY`、`FINNHUB_API_KEY`、`SEC_EDGAR_EMAIL`，把事件和新闻入口切到真实数据。
3. 然后部署远端 LLM：`REMOTE_LLM_URL` + `REMOTE_LLM_API_KEY`。
4. 最后做 ESG LoRA 的继续训练与评测。
