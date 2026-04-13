from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.p2_decision import P2_STRATEGY_SNAPSHOT_COLUMNS

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "advanced_decision"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "contextual_bandit"


def _evaluate(frame: pd.DataFrame, policies: dict[str, dict[str, np.ndarray]], alpha: float) -> dict[str, float]:
    daily_rewards: list[float] = []
    for _, day_slice in frame.groupby("date"):
        context = day_slice.iloc[0][P2_STRATEGY_SNAPSHOT_COLUMNS].to_numpy(dtype=np.float64)
        scores: list[tuple[str, float]] = []
        for arm, policy in policies.items():
            inv = np.linalg.inv(policy["A"])
            theta = inv @ policy["b"]
            score = float(theta @ context + alpha * np.sqrt(context @ inv @ context))
            scores.append((arm, score))
        chosen_arm = max(scores, key=lambda item: item[1])[0]
        chosen_row = day_slice[day_slice["arm"] == chosen_arm]
        if not chosen_row.empty:
            daily_rewards.append(float(chosen_row.iloc[0]["reward"]))
    if not daily_rewards:
        return {"mean_reward": 0.0, "hit_rate": 0.0}
    series = pd.Series(daily_rewards, dtype="float64")
    return {
        "mean_reward": round(float(series.mean()), 6),
        "hit_rate": round(float((series > 0).mean()), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a LinUCB contextual-bandit baseline for P2 strategy routing.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "bandit_contexts_train.csv"), help="Training csv path.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "bandit_contexts_val.csv"), help="Validation csv path.")
    parser.add_argument("--alpha", type=float, default=0.6, help="Exploration coefficient.")
    parser.add_argument("--ridge", type=float, default=1.0, help="Ridge regularization strength.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    args = parser.parse_args()

    train = pd.read_csv(args.train_csv)
    val = pd.read_csv(args.val_csv)
    arms = sorted(train["arm"].astype(str).unique().tolist())
    dimension = len(P2_STRATEGY_SNAPSHOT_COLUMNS)
    policies: dict[str, dict[str, np.ndarray]] = {
        arm: {
            "A": np.eye(dimension, dtype=np.float64) * args.ridge,
            "b": np.zeros(dimension, dtype=np.float64),
        }
        for arm in arms
    }

    for _, row in train.sort_values("date").iterrows():
        arm = str(row["arm"])
        context = row[P2_STRATEGY_SNAPSHOT_COLUMNS].to_numpy(dtype=np.float64)
        reward = float(row["reward"])
        policies[arm]["A"] += np.outer(context, context)
        policies[arm]["b"] += reward * context

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "alpha": args.alpha,
        "ridge": args.ridge,
        "arms": arms,
        "feature_names": P2_STRATEGY_SNAPSHOT_COLUMNS,
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "validation": _evaluate(val, policies, args.alpha),
    }
    serializable = {
        arm: {
            "A": policy["A"].tolist(),
            "b": policy["b"].tolist(),
        }
        for arm, policy in policies.items()
    }
    (output_dir / "policy.json").write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
