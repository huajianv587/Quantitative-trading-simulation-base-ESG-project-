# 云端训练资产说明

这份项目现在已经把除真实训练权重之外的大部分资产准备好了。你后续在 5090 云机上训练时，优先看这几个入口：

- `training/cloud_assets/master_training_manifest.json`
- `training/cloud_assets/scripts/download_public_models.sh`
- `delivery/cloud_training_bundle/README.md`

## 训练顺序

1. `Qwen/Qwen2.5-7B-Instruct` + ESG LoRA v2  
   数据：`data/rag_training_data/train.jsonl`、`data/rag_training_data/val.jsonl`

2. Alpha Ranker  
   数据：`data/alpha_ranker/*.csv`  
   模型：`xgboost` / `lightgbm` / `catboost`

3. P1 风险栈 + 序列预测  
   数据：`data/p1_stack/*.csv`  
   模型：tabular 套件 + `lstm` / `tcn`

4. 新闻 / controversy 分类器  
   数据：`data/event_classifier/*.csv` 与 `data/event_classifier/*/train.jsonl`  
   基座：`ProsusAI/finbert`、`microsoft/deberta-v3-base`

5. P2 策略选择器  
   数据：`data/p2_stack/*.csv`  
   模型：`xgboost` / `lightgbm` / `catboost`

6. 高级决策层  
   数据：`data/advanced_decision/*`  
   模型：GNN / contextual bandit / PPO  
   说明：这一层目前提供的是 bootstrap 数据和训练骨架，GNN / PPO 没有固定 Hugging Face base model，通常从头训。

## 已准备好的数据

- `data/rag_training_data`
- `data/alpha_ranker`
- `data/p1_stack`
- `data/p2_stack`
- `data/event_classifier`
- `data/advanced_decision`

## 已准备好的脚本

- LoRA：`training/finetune.py`
- Alpha：`training/train_alpha_ranker.py`
- P1：`training/train_p1_stack.py`
- Sequence：`training/train_sequence_forecaster.py`
- Event Classifier：`training/train_event_classifier.py`
- P2：`training/train_p2_selector.py`
- Advanced Decision：`training/train_contextual_bandit.py`

## 公共基座模型

建议直接在云机上下载：

- `Qwen/Qwen2.5-7B-Instruct`
- `ProsusAI/finbert`
- `microsoft/deberta-v3-base`
- `BAAI/bge-m3`
- `Alibaba-NLP/gte-Qwen2-1.5B-instruct`

如果你想直接复制本地已下载的小模型，本地已有：

- `training/p0_assets/models/finbert`
- `training/p0_assets/models/deberta-v3-base`

## 一键入口

先生成清单和下载脚本：

```bash
python training/download_all_training_assets.py
```

再生成可复制 bundle：

```bash
python training/build_cloud_training_bundle.py --include-local-models
```

生成结果在：

- `training/cloud_assets`
- `delivery/cloud_training_bundle`

## 说明

- `event_classifier` 数据集是根据 P2 信号特征合成的 bootstrap 文本集，可以先训练通链路，但后面最好补真实新闻和 controversy 标注。
- `advanced_decision` 当前重点是把 GNN / bandit / PPO 的训练输入形态准备好，不是说这层已经有最终高质量标签。
