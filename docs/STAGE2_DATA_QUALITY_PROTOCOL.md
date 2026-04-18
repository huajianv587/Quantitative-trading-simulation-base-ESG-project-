# Stage 2 Data Quality Protocol

Stage 2 upgrades the non-paper model lines to paper-grade data quality after the
Stage 1 ESG/RL paper-run has completed.

## Boundary

- Stage 1 trains the full project and produces formal ESG/RL paper results.
- Stage 1 checkpoints for LoRA, Event, Alpha, P1, and P2 are baseline project
  checkpoints, not paper-grade evidence.
- Stage 2 prepares and audits upgraded data for LoRA, Event, Alpha, P1, and P2.
- Stage 2 must not rewrite Stage 1 paper-run inputs, outputs, or frozen
  manifests.

## Paper-Grade Rules

- Universe defaults to the 20 ESG/RL companies.
- Timeline defaults to train `2022-01-01` to `2023-12-31`, validation
  `2024-01-01` to `2024-12-31`, and test `2025-01-01` to `2025-12-31`.
- The 2025 test split must not be used for tuning, prompt design, feature
  selection, manual rule changes, or model selection.
- Every record needs source, provider, timestamp, checksum, license or usage
  note, and raw-to-processed lineage.
- Every paper-grade training line needs an independent test split.
- Weak labels are allowed only if their generation rule, confidence, reviewer
  status, and adjudication trail are recorded.

## Track Requirements

- LoRA: instruction data must be source-linked to ESG reports, RAG evidence
  chains, or scored explanation chains. Source chunks cannot cross splits.
- Event classifier: labels must come from real news, filings, announcements, or
  controversy sources. At least 10% of records require dual review. Cohen's
  kappa target is `>=0.70`.
- Alpha/P1/P2: features must be point-in-time. Forward returns, volatility,
  drawdown, regime labels, and strategy labels must only use information
  available before the prediction horizon.

## Required Artifacts

- `storage/stage2_data_quality/stage2_data_manifest.json`
- `storage/stage2_data_quality/audit/stage2_data_audit.json`
- `storage/stage2_data_quality/label_queue/*.csv`
- `storage/stage2_data_quality/adjudication/*.csv`
- `storage/stage2_data_quality/split_manifest.json`

The Stage 2 audit is allowed to fail until real data collection and review are
complete. A failed Stage 2 audit must not block Stage 1 paper-run packaging.
