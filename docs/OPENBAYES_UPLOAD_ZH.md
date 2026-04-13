# OpenBayes 上传说明

当前项目已经准备好一套可上传到 OpenBayes 的 P0 训练包，目标数据集为 `HucMvPZuFf0`。

## 1. 训练包内容

- `data/alpha_ranker/`
  - XGBoost / LightGBM alpha ranker 训练集、验证集、manifest
- `data/rag_training_data/`
  - ESG LoRA 继续训练语料 `train.jsonl` / `val.jsonl`
- `training/*.py`
  - Alpha 数据准备、训练、评估脚本
  - ESG LoRA 训练脚本
- `training/p0_assets/*.json|*.sh`
  - 模型清单、数据清单、Colab 下载脚本
- `model-serving/checkpoint/alpha_ranker/`
  - 当前本地 baseline alpha ranker checkpoint

## 2. 先构建上传包

```bash
python scripts/build_openbayes_dataset.py --clean
```

如果你希望把已经下载好的 `FinBERT` 和 `DeBERTa` 一起打进训练包：

```bash
python scripts/build_openbayes_dataset.py --clean --include-local-models
```

默认输出目录：

```text
delivery/openbayes/esg_quant_p0_training_bundle
```

## 3. 配置 OpenBayes token

把下面几项写进项目根目录 `.env`：

```env
OPENBAYES_TOKEN=你的token
OPENBAYES_DATASET_ID=HucMvPZuFf0
OPENBAYES_DATASET_VERSION=1
```

## 4. 一键上传

```bash
python scripts/upload_openbayes_dataset.py --rebuild
```

如果还要把本地模型材料一起上传：

```bash
python scripts/upload_openbayes_dataset.py --rebuild --include-local-models
```

## 5. 直接使用 bayes CLI

如果你想自己手动跑 CLI：

```bash
bayes login $OPENBAYES_TOKEN
bayes data upload HucMvPZuFf0 --version 1 --path delivery/openbayes/esg_quant_p0_training_bundle
```

## 6. 上传后建议训练顺序

1. 先训练 `alpha ranker`
2. 再训练 `Qwen/Qwen2.5-7B-Instruct` 的 ESG LoRA
3. 训练完成后把权重放回：
   - `model-serving/checkpoint/alpha_ranker/`
   - `model-serving/checkpoint/<你的lora目录>/`
