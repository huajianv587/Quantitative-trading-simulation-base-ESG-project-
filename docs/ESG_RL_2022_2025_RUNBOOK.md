# ESG/RL 2022-2025 Experiment Runbook

This is the operational path for the SCI experiment line:

```text
ESG reports -> OpenAI embeddings -> RAG evidence chain -> JHJ House Score V2/V2.1
-> daily RL features -> AutoDL training -> contribution statistics -> paper tables
```

## 1. Timeline

- Train: `2022-01-01` to `2023-12-31`
- Validation: `2024-01-01` to `2024-12-31`
- Test: `2025-01-01` to `2025-12-31`

The 2025 test set must not be used for Optuna, feature design, manual tuning, or model selection.

## 2. ESG Report Folder Contract

The formal corpus root is:

```text
esg_reports/<TICKER>/<YEAR>/
```

Flat files such as `esg_reports/MSFT/MSFT_2024_Sustainability_Report.pdf` are also accepted. `esg_reports/Apple/` is mapped to `AAPL`.

Recommended metadata file:

```text
esg_reports/MSFT/2024/source_url.txt
source_url=https://...
published_date=2025-03-15
```

The 20-stock universe is fixed:

```text
AAPL, MSFT, NVDA, GOOGL,
JPM, BAC, GS, MS,
XOM, CVX, NEE, ENPH,
AMZN, WMT, COST, PG,
JNJ, PFE, UNH, ABT
```

Missing reports must stay missing. The manifest marks them as `missing`, `source_unavailable`, or `not_published_yet`; the scoring layer uses neutral missing values instead of fake low scores.

## 3. Local ESG Commands

Build coverage and manifest:

```powershell
python scripts/esg_corpus_pipeline.py coverage --corpus-root esg_reports
```

Embedding with the formal paper model:

```powershell
python scripts/esg_corpus_pipeline.py embed --corpus-root esg_reports --embedding-model text-embedding-3-large
```

RAG evidence chain:

```powershell
python scripts/esg_corpus_pipeline.py rag-check --corpus-root esg_reports --evidence-chain
```

House Score V2 + V2.1:

```powershell
python scripts/esg_corpus_pipeline.py score --corpus-root esg_reports
```

Full local corpus pipeline:

```powershell
python scripts/esg_corpus_pipeline.py all --corpus-root esg_reports --embedding-model text-embedding-3-large --evidence-chain
```

Main artifacts:

```text
storage/esg_corpus/manifest.json
storage/esg_corpus/coverage_report.json
storage/esg_corpus/evidence_chain_report.json
storage/esg_corpus/house_scores_v2.json
storage/esg_corpus/house_scores_v2.csv
storage/esg_corpus/score_distribution_evidence_only.json
storage/rag/esg_reports_openai_3072/embeddings.jsonl
```

## 4. Formula Contract

`JHJ_HOUSE_SCORE_V2` remains the engineering baseline.

`JHJ_HOUSE_SCORE_V2_1_CALIBRATED` adds sector-year calibration:

- It uses only ESG evidence, support strength, confidence, staleness, and same-year cross-sectional score distribution.
- It does not look at returns or backtest metrics.
- Missing evidence stays neutral: `house_score_v2_1=50`, `esg_confidence=0`, `esg_missing_flag=1`.

Daily RL datasets include:

```text
house_score_v2
house_score_v2_1
esg_delta
esg_delta_v2_1
esg_confidence
esg_staleness_days
esg_missing_flag
sector_relative_esg
```

## 5. Time Alignment Rule

An ESG score becomes available only on:

```text
published_date + 1 trading day
```

Before the first effective report, the row uses neutral ESG values and `esg_missing_flag = 1`. This prevents time leakage.

## 6. Paper-Run Data Pipeline

Build formal datasets and quality reports:

```powershell
python scripts/run_esg_rl_2022_2025_pipeline.py `
  --run-namespace paper-run `
  --sample full_2022_2025 `
  --corpus-root esg_reports `
  --build-datasets
```

Robustness sample:

```powershell
python scripts/run_esg_rl_2022_2025_pipeline.py `
  --run-namespace paper-run `
  --sample post_esg_effective `
  --corpus-root esg_reports `
  --build-datasets
```

`paper-run` blocks formal training if coverage, embedding, OHLCV provider, date alignment, or ESG/no-ESG isolation fails.

## 7. AutoDL 5090

Use SSH Key access, not a long-lived plaintext password.

Recommended instance image:

```text
Basic image / PyTorch 2.8.0 / Python 3.12 / Ubuntu 22.04 / 1x RTX 5090
```

If AutoDL offers a Python 3.11 PyTorch 2.8 image, Python 3.11 is still the lowest-risk choice. The current scripts also support the selected Python 3.12 image. The bootstrap script creates `.venv` with `--system-site-packages` so it reuses the image's CUDA-enabled PyTorch instead of reinstalling another large torch wheel.

On AutoDL, after syncing the repo and `.env`:

```bash
bash scripts/autodl_bootstrap.sh
```

Run the formal driver:

```bash
bash scripts/autodl_run_paper_experiments.sh
```

Run the complete Stage 1 driver when you want the paper-run plus every
project training line in one resumable 5090 pass:

```bash
TOTAL_STEPS=500000 EPISODES=50 RUN_EMBED=0 bash scripts/run_5090_stage1_all.sh
```

Optional controls:

```bash
RUN_EMBED=1 TOTAL_STEPS=500000 EPISODES=50 bash scripts/autodl_run_paper_experiments.sh
SAMPLES="full_2022_2025" SMOKE=1 bash scripts/autodl_run_paper_experiments.sh
SMOKE=1 ALLOW_CPU_SMOKE=1 bash scripts/run_5090_stage1_all.sh
```

V2 and V2.1 results are isolated under:

```text
storage/quant/rl-experiments/paper-run/formula_v2/sample_full_2022_2025/
storage/quant/rl-experiments/paper-run/formula_v2/sample_post_esg_effective/
storage/quant/rl-experiments/paper-run/formula_v2_1/sample_full_2022_2025/
storage/quant/rl-experiments/paper-run/formula_v2_1/sample_post_esg_effective/
```

`paper-run` requires CUDA by default. A CPU-only run is allowed only for an explicit smoke check:

```bash
ALLOW_CPU_SMOKE=1 SMOKE=1 bash scripts/autodl_run_paper_experiments.sh
```

Final preflight:

```bash
python scripts/quant_rl_paper_preflight.py --namespace paper-run --sample full_2022_2025 --require-cuda
python scripts/quant_rl_paper_preflight.py --namespace paper-run --sample post_esg_effective --require-cuda
```

## 8. Experiment Groups

- `B1_buyhold`
- `B2_macd`
- `B3_sac_noesg`
- `B4_sac_esg`
- `OURS_full`
- `6a_no_esg_obs`
- `6b_no_esg_reward`
- `6c_no_regime`

Summarize contribution:

```powershell
python scripts/quant_rl_esg_contribution_report.py --run-namespace paper-run --sample full_2022_2025 --formula-mode v2
python scripts/quant_rl_esg_contribution_report.py --run-namespace paper-run --sample full_2022_2025 --formula-mode v2_1
```

The final paper can support both outcomes:

- Positive result: ESG improves Sharpe and/or drawdown.
- Negative result: annual RAG ESG is too low-frequency for short-horizon RL, motivating higher-frequency ESG proxies.
