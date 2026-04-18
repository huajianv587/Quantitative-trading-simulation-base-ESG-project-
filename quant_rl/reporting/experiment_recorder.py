from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


MANUAL_STOCK_UNIVERSE = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL"],
    "Finance": ["JPM", "BAC", "GS", "MS"],
    "Energy": ["XOM", "CVX", "NEE", "ENPH"],
    "Consumer": ["AMZN", "WMT", "COST", "PG"],
    "Healthcare": ["JNJ", "PFE", "UNH", "ABT"],
}

EXPERIMENT_GROUPS = {
    "B1_buyhold": {"label": "B1 Buy&Hold", "family": "main", "seeds": [None], "algorithm": "buy_hold"},
    "B2_macd": {"label": "B2 MACD", "family": "main", "seeds": [None], "algorithm": "rule_based"},
    "B3_sac_noesg": {"label": "B3 SAC noESG", "family": "main", "seeds": [42, 123, 456], "algorithm": "sac"},
    "B4_sac_esg": {"label": "B4 SAC+ESG", "family": "main", "seeds": [42, 123, 456], "algorithm": "sac"},
    "OURS_full": {"label": "OURS Full", "family": "main", "seeds": [42, 123, 456], "algorithm": "hybrid_frontier"},
    "6a_no_esg_obs": {"label": "6a No ESG Obs", "family": "ablation", "seeds": [42, 123, 456], "algorithm": "sac"},
    "6b_no_esg_reward": {"label": "6b No ESG Reward", "family": "ablation", "seeds": [42, 123, 456], "algorithm": "sac"},
    "6c_no_regime": {"label": "6c No Regime", "family": "ablation", "seeds": [42, 123, 456], "algorithm": "sac"},
}


def build_protocol_summary(output_root: str | Path) -> dict[str, Any]:
    output_root = Path(output_root)
    return {
        "paper_title": "ESG-Augmented Reinforcement Learning with Regime-Aware Multi-Agent Routing for Quantitative Equity Trading",
        "target_journal": "Intelligent Systems with Applications (Q2)",
        "total_training_runs": 18,
        "seeds": [42, 123, 456],
        "time_split": {
            "train": ["2022-01-01", "2023-12-31"],
            "validation": ["2024-01-01", "2024-12-31"],
            "test": ["2025-01-01", "2025-12-31"],
        },
        "stock_universe": MANUAL_STOCK_UNIVERSE,
        "groups": EXPERIMENT_GROUPS,
        "recording_requirements": [
            "metrics.json for every run",
            "equity_curve.csv for every run",
            "all_results.xlsx summary workbook",
            "Optuna best params and validation Sharpe",
            "training time and stability notes",
        ],
        "output_root": str(output_root),
        "output_structure": {
            "data": ["raw", "processed", "esg"],
            "results": list(EXPERIMENT_GROUPS.keys()),
            "summary": ["all_results.xlsx"],
        },
    }


@dataclass(slots=True)
class ExperimentRecorder:
    output_root: Path

    def __post_init__(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.results_root.mkdir(parents=True, exist_ok=True)
        self.summary_root.mkdir(parents=True, exist_ok=True)

    @property
    def data_root(self) -> Path:
        return self.output_root / "data"

    @property
    def results_root(self) -> Path:
        return self.output_root / "results"

    @property
    def summary_root(self) -> Path:
        return self.output_root / "summary"

    def protocol(self) -> dict[str, Any]:
        return build_protocol_summary(self.output_root)

    def record_dataset_manifest(self, payload: dict[str, Any], name: str = "manifest.json") -> str:
        self.data_root.mkdir(parents=True, exist_ok=True)
        path = self.data_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def run_dir(self, group: str, seed: int | None = None) -> Path:
        base = self.results_root / group
        if seed is None:
            path = base
        else:
            path = base / f"seed{seed}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def record_result(
        self,
        *,
        group: str,
        seed: int | None,
        metrics: dict[str, Any],
        history: pd.DataFrame | None = None,
        checkpoint_path: str | None = None,
        notes: str | None = None,
        training: dict[str, Any] | None = None,
        significance: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        target_dir = self.run_dir(group, seed)
        metrics_payload = self._manual_metrics_payload(
            group=group,
            seed=seed,
            metrics=metrics,
            history=history,
            notes=notes,
            training=training,
            significance=significance,
            checkpoint_path=checkpoint_path,
            artifacts=artifacts,
        )
        metrics_path = target_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        outputs = {"metrics_json": str(metrics_path)}
        if history is not None and not history.empty:
            curve = self._format_equity_curve(history)
            curve_path = target_dir / "equity_curve.csv"
            curve.to_csv(curve_path, index=False)
            outputs["equity_curve_csv"] = str(curve_path)

        workbook = self.build_summary_workbook()
        outputs["summary_workbook"] = workbook
        return outputs

    def build_summary_workbook(self) -> str:
        rows = self._collect_metric_rows()
        workbook_path = self.summary_root / "all_results.xlsx"
        with pd.ExcelWriter(workbook_path) as writer:
            self._sheet_for_family(rows, "main").to_excel(writer, sheet_name="Main Results", index=False)
            self._sheet_for_family(rows, "ablation").to_excel(writer, sheet_name="Ablation Results", index=False)
            self._build_equity_curve_sheet().to_excel(writer, sheet_name="Equity Curves", index=False)
        return str(workbook_path)

    def output_status(self) -> dict[str, Any]:
        metrics_files = list(self.results_root.rglob("metrics.json"))
        curves = list(self.results_root.rglob("equity_curve.csv"))
        manifests = list(self.data_root.rglob("manifest*.json"))
        workbook = self.summary_root / "all_results.xlsx"
        return {
            "output_root": str(self.output_root),
            "dataset_manifests": len(manifests),
            "metrics_files": len(metrics_files),
            "equity_curves": len(curves),
            "summary_workbook": str(workbook),
            "summary_exists": workbook.exists(),
        }

    def _manual_metrics_payload(
        self,
        *,
        group: str,
        seed: int | None,
        metrics: dict[str, Any],
        history: pd.DataFrame | None,
        notes: str | None,
        training: dict[str, Any] | None,
        significance: dict[str, Any] | None,
        checkpoint_path: str | None,
        artifacts: dict[str, Any] | None,
    ) -> dict[str, Any]:
        returns = pd.Series(dtype=float)
        if history is not None and not history.empty and "equity" in history.columns:
            returns = history["equity"].astype(float).pct_change().dropna()
        avg_win_loss_ratio = None
        if not returns.empty:
            wins = returns[returns > 0]
            losses = returns[returns < 0].abs()
            if not wins.empty and not losses.empty:
                avg_win_loss_ratio = float(wins.mean() / max(losses.mean(), 1e-8))

        payload = {
            "group": group,
            "seed": seed,
            "annual_return": float(metrics.get("annualized_return", metrics.get("annual_return", 0.0)) or 0.0),
            "sharpe_ratio": float(metrics.get("sharpe", metrics.get("sharpe_ratio", 0.0)) or 0.0),
            "sortino_ratio": float(metrics.get("sortino", metrics.get("sortino_ratio", 0.0)) or 0.0),
            "max_drawdown": float(metrics.get("max_drawdown", 0.0) or 0.0),
            "calmar_ratio": float(metrics.get("calmar", metrics.get("calmar_ratio", 0.0)) or 0.0),
            "turnover_rate": float(metrics.get("avg_turnover", metrics.get("turnover_rate", 0.0)) or 0.0),
            "win_rate": float(metrics.get("win_rate", 0.0) or 0.0),
            "avg_win_loss_ratio": avg_win_loss_ratio,
            "t_stat_vs_B4": significance.get("t_stat") if significance else None,
            "p_value_vs_B4": significance.get("p_value") if significance else None,
            "significant": significance.get("significant") if significance else None,
            "final_train_reward": training.get("final_train_reward") if training else None,
            "training_minutes": training.get("training_minutes") if training else None,
            "optuna_best_trial": training.get("optuna_best_trial") if training else None,
            "optuna_best_val_sharpe": training.get("optuna_best_val_sharpe") if training else None,
            "checkpoint_path": checkpoint_path,
            "artifacts": artifacts or {},
            "notes": notes or "",
        }
        return payload

    def _collect_metric_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for metrics_path in sorted(self.results_root.rglob("metrics.json")):
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            group = str(payload.get("group") or metrics_path.parent.parent.name)
            family = EXPERIMENT_GROUPS.get(group, {}).get("family", "main")
            rows.append(
                {
                    "Group": EXPERIMENT_GROUPS.get(group, {}).get("label", group),
                    "GroupKey": group,
                    "Family": family,
                    "Seed": payload.get("seed"),
                    "Annual Ret": payload.get("annual_return"),
                    "Sharpe": payload.get("sharpe_ratio"),
                    "Sortino": payload.get("sortino_ratio"),
                    "Max DD": payload.get("max_drawdown"),
                    "Calmar": payload.get("calmar_ratio"),
                    "Turnover": payload.get("turnover_rate"),
                    "Win Rate": payload.get("win_rate"),
                    "p-value": payload.get("p_value_vs_B4"),
                }
            )
        return rows

    def _sheet_for_family(self, rows: list[dict[str, Any]], family: str) -> pd.DataFrame:
        filtered = [row for row in rows if row["Family"] == family]
        if not filtered:
            return pd.DataFrame(columns=["Group", "Seed", "Annual Ret", "Sharpe", "Sortino", "Max DD", "Calmar", "p-value"])

        df = pd.DataFrame(filtered)
        display_rows: list[dict[str, Any]] = []
        for group_key, group_df in df.groupby("GroupKey", sort=False):
            label = EXPERIMENT_GROUPS.get(group_key, {}).get("label", group_key)
            group_df = group_df.sort_values(by="Seed", key=lambda series: pd.to_numeric(series, errors="coerce").fillna(-1))
            for _, row in group_df.iterrows():
                display_rows.append(
                    {
                        "Group": label,
                        "Seed": row["Seed"],
                        "Annual Ret": row["Annual Ret"],
                        "Sharpe": row["Sharpe"],
                        "Sortino": row["Sortino"],
                        "Max DD": row["Max DD"],
                        "Calmar": row["Calmar"],
                        "p-value": row["p-value"],
                    }
                )

            if group_df["Seed"].notna().sum() > 1:
                numeric_cols = ["Annual Ret", "Sharpe", "Sortino", "Max DD", "Calmar"]
                means = group_df[numeric_cols].mean(numeric_only=True)
                stds = group_df[numeric_cols].std(numeric_only=True, ddof=0)
                display_rows.append(
                    {
                        "Group": f"{label} MEAN±STD",
                        "Seed": "avg",
                        "Annual Ret": f"{means['Annual Ret']:.4f} ± {stds['Annual Ret']:.4f}",
                        "Sharpe": f"{means['Sharpe']:.4f} ± {stds['Sharpe']:.4f}",
                        "Sortino": f"{means['Sortino']:.4f} ± {stds['Sortino']:.4f}",
                        "Max DD": f"{means['Max DD']:.4f} ± {stds['Max DD']:.4f}",
                        "Calmar": f"{means['Calmar']:.4f} ± {stds['Calmar']:.4f}",
                        "p-value": "",
                    }
                )
        return pd.DataFrame(display_rows)

    def _build_equity_curve_sheet(self) -> pd.DataFrame:
        grouped: dict[str, list[pd.DataFrame]] = {}
        for curve_path in sorted(self.results_root.rglob("equity_curve.csv")):
            group = curve_path.parent.parent.name if curve_path.parent.name.startswith("seed") else curve_path.parent.name
            frame = pd.read_csv(curve_path)
            if "date" not in frame.columns or "portfolio_value" not in frame.columns:
                continue
            compact = frame[["date", "portfolio_value"]].copy()
            compact["portfolio_value"] = pd.to_numeric(compact["portfolio_value"], errors="coerce")
            compact = compact.dropna(subset=["date", "portfolio_value"]).groupby("date", as_index=False).last()
            grouped.setdefault(group, []).append(compact.rename(columns={"portfolio_value": curve_path.stem}))

        if not grouped:
            return pd.DataFrame(columns=["date"])

        merged = None
        for group, frames in grouped.items():
            aligned = None
            for frame in frames:
                aligned = frame if aligned is None else aligned.merge(frame, on="date", how="outer")
            assert aligned is not None
            value_columns = [column for column in aligned.columns if column != "date"]
            aligned[group] = aligned[value_columns].mean(axis=1, numeric_only=True)
            aligned = aligned[["date", group]]
            merged = aligned if merged is None else merged.merge(aligned, on="date", how="outer")
        return merged.sort_values("date").reset_index(drop=True) if merged is not None else pd.DataFrame(columns=["date"])

    @staticmethod
    def _format_equity_curve(history: pd.DataFrame) -> pd.DataFrame:
        frame = history.copy()
        if "timestamp" in frame.columns:
            frame["date"] = pd.to_datetime(frame["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            frame["date"] = frame.index.astype(str)
        frame["portfolio_value"] = pd.to_numeric(frame.get("equity"), errors="coerce")
        frame["daily_return"] = frame["portfolio_value"].pct_change().fillna(0.0)
        if "position" not in frame.columns:
            frame["position"] = 0.0
        if "regime" not in frame.columns:
            frame["regime"] = ""
        frame = frame[["date", "portfolio_value", "daily_return", "position", "regime"]].dropna(subset=["portfolio_value"])
        if frame.empty:
            return frame
        frame["portfolio_value"] = pd.to_numeric(frame["portfolio_value"], errors="coerce")
        frame["daily_return"] = pd.to_numeric(frame["daily_return"], errors="coerce").fillna(0.0)
        frame["position"] = pd.to_numeric(frame["position"], errors="coerce").fillna(0.0)
        return (
            frame.dropna(subset=["portfolio_value"])
            .groupby("date", as_index=False)
            .agg(
                portfolio_value=("portfolio_value", "last"),
                daily_return=("daily_return", "last"),
                position=("position", "mean"),
                regime=("regime", "last"),
            )
        )
