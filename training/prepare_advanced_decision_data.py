from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.p2_decision import P2_STRATEGY_PROFILES, P2_STRATEGY_SNAPSHOT_COLUMNS
from training.prepare_alpha_data import DEFAULT_SYMBOLS, split_dataset
from training.prepare_p1_data import build_p1_dataset
from training.prepare_p2_data import build_snapshot_frame, enrich_signal_frame

DEFAULT_INPUT_CSV = PROJECT_ROOT / "data" / "p2_stack" / "full_signal_dataset.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "advanced_decision"

SYMBOL_SECTOR = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "TSLA": "Consumer Discretionary",
    "NVDA": "Technology",
    "JPM": "Financials",
    "NEE": "Utilities",
    "PG": "Consumer Staples",
    "UNH": "Healthcare",
}


def _ensure_signal_frame(path: Path, symbols: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    p1_frame, _ = build_p1_dataset(symbols, history_days=420, short_window=20, long_window=60)
    return enrich_signal_frame(p1_frame)


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _attach_sector(frame: pd.DataFrame) -> pd.DataFrame:
    local = frame.copy()
    local["sector"] = [SYMBOL_SECTOR.get(str(symbol).upper(), "Unknown") for symbol in local["symbol"]]
    return local


def build_graph_nodes(signal_frame: pd.DataFrame) -> pd.DataFrame:
    local = _attach_sector(signal_frame)
    local["graph_reward_5d"] = (
        local["forward_return_5d"]
        - local["future_volatility_10d"] * 0.20
        - local["future_max_drawdown_20d"] * 0.24
    ).clip(-0.40, 0.40)
    keep = [
        "date",
        "symbol",
        "sector",
        "strategy_label",
        "p1_stack_score",
        "graph_centrality",
        "graph_contagion_risk",
        "graph_diversification_score",
        "graph_influence_score",
        "predicted_return_1d",
        "predicted_return_5d",
        "predicted_volatility_10d",
        "predicted_drawdown_20d",
        "forward_return_5d",
        "future_volatility_10d",
        "future_max_drawdown_20d",
        "graph_reward_5d",
    ]
    return local[keep].sort_values(["date", "symbol"]).reset_index(drop=True)


def build_graph_edges(signal_frame: pd.DataFrame, edge_threshold: float = 0.58) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    local = _attach_sector(signal_frame)
    for current_date, day_slice in local.groupby("date"):
        records = day_slice.to_dict("records")
        for left, right in combinations(records, 2):
            same_sector = 0.34 if left["sector"] == right["sector"] else 0.0
            p1_similarity = 1.0 - min(abs(float(left["p1_stack_score"]) - float(right["p1_stack_score"])), 1.0)
            return_similarity = 1.0 - min(abs(float(left["forward_return_5d"]) - float(right["forward_return_5d"])) / 0.25, 1.0)
            risk_similarity = 1.0 - min(
                abs(float(left["graph_contagion_risk"]) - float(right["graph_contagion_risk"])),
                1.0,
            )
            weight = _bounded(
                same_sector + 0.26 * p1_similarity + 0.20 * return_similarity + 0.20 * risk_similarity,
                0.0,
                1.0,
            )
            if weight < edge_threshold:
                continue
            rows.append(
                {
                    "date": current_date,
                    "source": left["symbol"],
                    "target": right["symbol"],
                    "source_sector": left["sector"],
                    "target_sector": right["sector"],
                    "weight": round(weight, 6),
                    "relationship": "peer_cluster" if left["sector"] == right["sector"] else "factor_similarity",
                }
            )
    return pd.DataFrame(rows).sort_values(["date", "weight"], ascending=[True, False]).reset_index(drop=True)


def build_bandit_contexts(signal_frame: pd.DataFrame) -> pd.DataFrame:
    snapshots = build_snapshot_frame(signal_frame)
    rows: list[dict[str, object]] = []
    for _, snapshot in snapshots.iterrows():
        current_date = str(snapshot["date"])
        day_slice = signal_frame[signal_frame["date"] == current_date].copy()
        if day_slice.empty:
            continue
        for strategy_key in P2_STRATEGY_PROFILES:
            if strategy_key == "defensive_quality":
                candidate = day_slice.sort_values(
                    ["future_max_drawdown_20d", "future_volatility_10d", "p1_stack_score"],
                    ascending=[True, True, False],
                ).head(2)
            elif strategy_key == "momentum_leaders":
                candidate = day_slice.sort_values(
                    ["forward_return_5d", "momentum", "p1_stack_score"],
                    ascending=[False, False, False],
                ).head(2)
            elif strategy_key == "diversified_barbell":
                candidate = day_slice.sort_values(
                    ["graph_diversification_score", "p1_stack_score"],
                    ascending=[False, False],
                ).head(2)
            else:
                candidate = day_slice.sort_values(
                    ["p1_stack_score", "forward_return_5d"],
                    ascending=[False, False],
                ).head(2)
            reward = float(
                (
                    candidate["forward_return_5d"]
                    - candidate["future_max_drawdown_20d"] * 0.24
                    - candidate["future_volatility_10d"] * 0.18
                ).mean()
                if not candidate.empty
                else 0.0
            )
            row = {column: snapshot[column] for column in P2_STRATEGY_SNAPSHOT_COLUMNS}
            row.update(
                {
                    "date": current_date,
                    "arm": strategy_key,
                    "reward": round(reward, 6),
                    "chosen_label": str(snapshot["strategy_label"]),
                    "is_target_arm": 1 if strategy_key == str(snapshot["strategy_label"]) else 0,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["date", "arm"]).reset_index(drop=True)


def build_ppo_episodes(signal_frame: pd.DataFrame, bandit_contexts: pd.DataFrame) -> list[dict[str, object]]:
    episodes: list[dict[str, object]] = []
    grouped_contexts = bandit_contexts.groupby("date")
    dates = sorted(grouped_contexts.groups.keys())
    for index, current_date in enumerate(dates):
        context_slice = grouped_contexts.get_group(current_date)
        state = {column: float(context_slice.iloc[0][column]) for column in P2_STRATEGY_SNAPSHOT_COLUMNS}
        best_row = context_slice.sort_values("reward", ascending=False).iloc[0]
        candidate_symbols = (
            signal_frame[signal_frame["date"] == current_date]
            .sort_values(["p1_stack_score", "forward_return_5d"], ascending=[False, False])
            .head(3)["symbol"]
            .astype(str)
            .tolist()
        )
        episodes.append(
            {
                "date": current_date,
                "state": state,
                "action": str(best_row["arm"]),
                "reward": float(best_row["reward"]),
                "candidate_symbols": candidate_symbols,
                "done": index == len(dates) - 1,
            }
        )
    return episodes


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare graph / bandit / PPO bootstrap assets for advanced decision training.")
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT_CSV), help="Source P2 signal dataset.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Fallback symbols when the source csv is missing.")
    parser.add_argument("--val-fraction", type=float, default=0.2, help="Validation split fraction.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    signal_frame = _ensure_signal_frame(Path(args.input_csv), symbols)
    graph_nodes = build_graph_nodes(signal_frame)
    graph_edges = build_graph_edges(signal_frame)
    bandit_contexts = build_bandit_contexts(signal_frame)
    ppo_episodes = build_ppo_episodes(signal_frame, bandit_contexts)

    nodes_train, nodes_val = split_dataset(graph_nodes, args.val_fraction)
    bandit_train, bandit_val = split_dataset(bandit_contexts, args.val_fraction)

    graph_nodes.to_csv(output_dir / "graph_nodes.csv", index=False)
    nodes_train.to_csv(output_dir / "graph_nodes_train.csv", index=False)
    nodes_val.to_csv(output_dir / "graph_nodes_val.csv", index=False)
    graph_edges.to_csv(output_dir / "graph_edges.csv", index=False)
    bandit_contexts.to_csv(output_dir / "bandit_contexts.csv", index=False)
    bandit_train.to_csv(output_dir / "bandit_contexts_train.csv", index=False)
    bandit_val.to_csv(output_dir / "bandit_contexts_val.csv", index=False)
    with (output_dir / "ppo_episodes.jsonl").open("w", encoding="utf-8") as handle:
        for payload in ppo_episodes:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "rows_graph_nodes": int(len(graph_nodes)),
        "rows_graph_edges": int(len(graph_edges)),
        "rows_bandit_contexts": int(len(bandit_contexts)),
        "rows_ppo_episodes": int(len(ppo_episodes)),
        "base_models": {
            "gnn": "no_pretrained_base_required",
            "bandit": "no_pretrained_base_required",
            "ppo": "no_pretrained_base_required",
        },
        "recommended_packages": [
            "torch-geometric",
            "networkx",
            "gymnasium",
            "stable-baselines3",
        ],
        "files": {
            "graph_nodes": str(output_dir / "graph_nodes.csv"),
            "graph_edges": str(output_dir / "graph_edges.csv"),
            "bandit_contexts": str(output_dir / "bandit_contexts.csv"),
            "ppo_episodes": str(output_dir / "ppo_episodes.jsonl"),
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
