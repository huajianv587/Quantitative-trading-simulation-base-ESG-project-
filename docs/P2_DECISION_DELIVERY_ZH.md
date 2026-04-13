# P2 决策栈交付说明

## 目标

P2 将现有 `alpha ranker -> P1 stack -> portfolio -> execution` 升级为：

`alpha ranker -> P1 alpha+risk -> P2 relationship graph -> strategy selector -> decision score -> portfolio -> paper execution`

## 已落地能力

- 关系图谱 runtime：基于行业、ESG、多因子、regime 与预期收益构建拓扑边和 contagion 指标
- 策略选择器 runtime：在 `momentum_leaders / balanced_quality_growth / diversified_barbell / defensive_quality` 之间切换
- 决策分数 runtime：输出 `decision_score`、`selector_priority_score`、`graph_contagion_risk`
- P2 API：
  - `GET /api/v1/quant/p2/status`
  - `POST /api/v1/quant/p2/decision/run`
- 前端控制台：
  - P2 状态卡
  - P2 决策报告卡
  - 图谱/策略 blocker 展示
- 训练骨架：
  - `training/prepare_p2_data.py`
  - `training/train_p2_selector.py`
  - `training/evaluate_p2_selector.py`
  - `training/download_p2_assets.py`

## 关键目录

- 数据：`data/p2_stack`
- checkpoint：`model-serving/checkpoint/p2_selector`
- runtime：`gateway/quant/p2_decision.py`

## 训练顺序建议

1. 先用更强的 P1 权重替换 `model-serving/checkpoint/p1_suite`
2. 再用 `training/prepare_p2_data.py` 生成 P2 数据集
3. 训练 `strategy_classifier`
4. 训练 `priority_regressor`
5. 将输出 checkpoint 覆盖到 `model-serving/checkpoint/p2_selector`

## 本地基线命令

```bash
python training/prepare_p2_data.py
python training/train_p2_selector.py --backend xgboost
python training/evaluate_p2_selector.py
python scripts/p2_stack_smoke.py
```

## 你后续训练完成后要回填的文件

- `model-serving/checkpoint/p2_selector/strategy_classifier/model.joblib`
- `model-serving/checkpoint/p2_selector/strategy_classifier/metadata.json`
- `model-serving/checkpoint/p2_selector/priority_regressor/model.joblib`
- `model-serving/checkpoint/p2_selector/priority_regressor/metadata.json`
- `model-serving/checkpoint/p2_selector/suite_manifest.json`
