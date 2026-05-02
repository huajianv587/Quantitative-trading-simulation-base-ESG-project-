# Blueprint Productionization Audit

## Runtime Boundary

The top-level blueprint folders remain compatibility adapters. Production behavior is now concentrated in `blueprint_runtime.py`, then exposed through `gateway/api/routers/quant.py` and the `/app` workbench.

## Public Endpoints

| Area | Endpoint | Web route |
| --- | --- | --- |
| Capability status | `GET /api/v1/quant/capabilities` | `#/capabilities` |
| Analysis | `POST /api/v1/quant/analysis/run` | `#/capabilities`, `#/factor-lab` |
| Models | `POST /api/v1/quant/models/train`, `POST /api/v1/quant/models/predict` | `#/capabilities`, `#/models` |
| Data | `POST /api/v1/quant/data/pipeline/run` | `#/capabilities`, `#/data-management` |
| Risk | `POST /api/v1/quant/risk/evaluate` | `#/capabilities`, `#/risk-board` |
| Backtest | `POST /api/v1/quant/backtest/advanced/run` | `#/capabilities`, `#/backtest` |
| Infrastructure | `POST /api/v1/quant/infrastructure/check` | `#/capabilities` |
| Reporting | `POST /api/v1/quant/reporting/build` | `#/capabilities`, `#/reports` |

## Module Coverage

| Module | Status behavior |
| --- | --- |
| `analysis/` | Computes technical metrics, factor IC/ICIR, numeric summaries, rankings, confidence, and expected return from supplied records or prices. |
| `models/` | Implements a uniform `fit/predict/evaluate/save/load` adapter contract for supervised, deep learning, RL, LoRA, and causal adapter classes. Optional heavy libraries are surfaced as degraded gaps instead of fake readiness. |
| `agents/` | Builds decision traces from quant overview, RAG/memory compatibility outputs, and selected signals. |
| `data/` | Produces governed datasets with source, quality, freshness, lineage, missing-value handling, dedupe, outlier flags, and feature-store-ready records. External feeds without credentials are reported as degraded capability gaps. |
| `risk/` | Evaluates drawdown, Sharpe, stress, CVaR, factor exposure, compliance, and model-risk checks with a `pass/blocked` execution gate. |
| `backtest/` | Runs transaction cost, attribution, counterfactual, and Monte Carlo advanced backtest components behind one endpoint. |
| `infrastructure/` | Checks MLflow, DVC, Optuna, drift, cost, and scheduler readiness, with local degraded operation when optional dependencies are missing. |
| `reporting/` | Builds JSON/HTML-ready portfolio, heatmap, risk dashboard, tearsheet, archive, benchmark, and factor report payloads. |
| `rag/api/database/notebooks` | Remain compatibility layers and are represented in capability status with health/configuration gaps. |

## Safety Rules

Paper execution remains behind existing execution gates. These blueprint endpoints do not submit live orders. Live trading routes must continue to return plans or recommendations only unless a separate explicitly confirmed live path is introduced.
