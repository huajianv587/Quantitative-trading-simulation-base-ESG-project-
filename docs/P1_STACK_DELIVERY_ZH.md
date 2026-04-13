# P1 Alpha + Risk Stack 交付说明

## 当前已完成

- 多模型 P1 运行时：`gateway/quant/p1_stack.py`
- 主链路接入：
  - `alpha ranker -> P1 stack -> portfolio construction`
  - API:
    - `GET /api/v1/quant/p1/status`
    - `POST /api/v1/quant/p1/stack/run`
- 前端控制台：
  - `frontend/js/pages/portfolio-lab.js`
  - 新增 P1 Stack 状态面板与运行入口
- 训练与评估骨架：
  - `training/prepare_p1_data.py`
  - `training/train_p1_stack.py`
  - `training/evaluate_p1_stack.py`
  - `training/run_p1_walk_forward.py`
  - `training/train_sequence_forecaster.py`
  - `training/download_p1_assets.py`
- 独立 smoke：
  - `scripts/p1_stack_smoke.py`

## 当前基线产物

- 数据集目录：`data/p1_stack`
- 多模型 suite checkpoint：`model-serving/checkpoint/p1_suite`
- 序列模型 baseline：`model-serving/checkpoint/sequence_forecaster`
- P1 资产 manifest：`training/p1_assets/p1_asset_manifest.json`

## 本地可直接执行

```bash
python training/prepare_p1_data.py
python training/train_p1_stack.py --backend auto
python training/evaluate_p1_stack.py
python training/run_p1_walk_forward.py --backend auto
python training/train_sequence_forecaster.py --full-csv data/p1_stack/full_dataset.csv --architecture lstm --epochs 1 --hidden-size 32 --output-dir model-serving/checkpoint/sequence_forecaster
python scripts/p1_stack_smoke.py
python scripts/runtime_doctor.py
```

## 你后续训练后要替换的目录

- Tabular P1 suite:
  - `model-serving/checkpoint/p1_suite/return_1d`
  - `model-serving/checkpoint/p1_suite/return_5d`
  - `model-serving/checkpoint/p1_suite/volatility_10d`
  - `model-serving/checkpoint/p1_suite/drawdown_20d`
  - `model-serving/checkpoint/p1_suite/regime_classifier`
- Sequence 模型：
  - `model-serving/checkpoint/sequence_forecaster`

## 推荐你在 GPU 上继续训练的方向

- `LightGBM / XGBoost / CatBoost`:
  - `forward_return_1d`
  - `forward_return_5d`
  - `future_volatility_10d`
  - `future_max_drawdown_20d`
  - `regime_label`
- `LSTM / TCN`:
  - return forecast
  - volatility forecast
- 文本与事件层：
  - `ProsusAI/finbert`
  - `microsoft/deberta-v3-base`
  - `BAAI/bge-m3`
  - `Alibaba-NLP/gte-Qwen2-1.5B-instruct`

## 运行时判定

- 如果 `p1_suite` checkpoint 可加载，系统会在研究、组合和 P1 report 中自动启用真实模型
- 如果 checkpoint 缺失，系统会自动退回 heuristic P1 scoring，不会阻断主链路
