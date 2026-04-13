# P0 Alpha Ranker Colab 训练说明

## 目标

把当前 P0 的规则信号层升级为一个可训练、可替换、可上线的 tabular alpha ranker。

当前线上约定：

- 训练数据目录：`data/alpha_ranker/`
- checkpoint 目录：`model-serving/checkpoint/alpha_ranker/`
- 线上运行时：`gateway/quant/alpha_ranker.py`

## 本地准备

先在项目根目录生成训练材料：

```bash
python training/prepare_alpha_data.py
python training/download_p0_assets.py
```

会生成：

- `data/alpha_ranker/train.csv`
- `data/alpha_ranker/val.csv`
- `data/alpha_ranker/manifest.json`
- `training/p0_assets/colab_download_p0_assets.sh`

## Colab 建议流程

```bash
git clone <your-repo>
cd Quantitative-trading-simulation-base-ESG-project
pip install -r training/requirements.txt
python training/train_alpha_ranker.py --backend xgboost
python training/evaluate_alpha_ranker.py
```

如果你要强制 LightGBM：

```bash
python training/train_alpha_ranker.py --backend lightgbm
```

## 训练完成后要带回来的文件

拷回本仓库：

- `model-serving/checkpoint/alpha_ranker/model.joblib`
- `model-serving/checkpoint/alpha_ranker/metadata.json`
- `model-serving/checkpoint/alpha_ranker/metrics.json`
- `model-serving/checkpoint/alpha_ranker/feature_importance.csv`
- `model-serving/checkpoint/alpha_ranker/evaluation.json`

## 训练建议

- P0 先用 `forward_return_5d`
- 如果样本量足够，再比较 `forward_return_20d`
- 先以 `xgboost` 为主，`lightgbm` 做对照
- 先追求稳定排序能力，再谈复杂 stacking

## 上线验证

把 checkpoint 放回后，本地执行：

```bash
python scripts/alpha_ranker_smoke.py
python scripts/runtime_doctor.py
python -m pytest -q
```

前端交易页和 `/api/v1/quant/execution/monitor` 也会显示 ranker 状态。
