from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import torch

from gateway.quant.market_data import MarketDataGateway
from gateway.scheduler.data_sources import DataSourceManager
from quant_rl.agents.dqn_agent import DQNAgent, DQNConfig
from quant_rl.agents.ppo_agent import PPOAgent, PPOConfig
from quant_rl.agents.sac_agent import SACAgent, SACConfig
from quant_rl.algorithms.decision_transformer import DecisionTransformerConfig, DecisionTransformerTrainer
from quant_rl.algorithms.iql import IQLConfig, IQLLearner
from quant_rl.algorithms.world_model import WorldModelConfig, WorldModelResearchAgent
from quant_rl.analysis.features import add_technical_features, default_feature_columns
from quant_rl.analysis.observation import ObservationBuilder
from quant_rl.backtest.engine import BacktestEngine
from quant_rl.backtest.environment import TradingEnv, TradingEnvConfig
from quant_rl.backtest.reports import build_backtest_reports
from quant_rl.backtest.rewards import RewardConfig
from quant_rl.data.contracts import Transition
from quant_rl.data.loaders import generate_synthetic_ohlcv, load_market_data
from quant_rl.data.split import time_split
from quant_rl.infrastructure.registry import get_artifact_store, get_run_repository
from quant_rl.infrastructure.settings import get_settings
from quant_rl.infrastructure.types import RunInfo
from quant_rl.reporting.experiment_recorder import EXPERIMENT_GROUPS, MANUAL_STOCK_UNIVERSE, ExperimentRecorder
from quant_rl.training.common import ReplayBuffer, set_seed
from quant_rl.training.dqn_trainer import DQNTrainConfig, DQNTrainer
from quant_rl.training.offline_trainer import OfflineCQLConfig, OfflineDQNTrainer
from quant_rl.training.ppo_trainer import PPOTrainConfig, PPOTrainer
from quant_rl.training.sac_trainer import SACTrainConfig, SACTrainer

try:
    from gateway.agents.esg_scorer import ESGScoringFramework
except Exception:  # pragma: no cover - optional runtime
    ESGScoringFramework = None


RECIPE_PRESETS: dict[str, dict[str, Any]] = {
    "L1_price_tech": {
        "label": "L1 Price + Tech Baseline",
        "symbols": ["AAPL"],
        "layers": ["price_tech"],
        "algorithm": "sac",
    },
    "L2_vol_sentiment": {
        "label": "L2 Price + VIX + Put/Call",
        "symbols": ["AAPL"],
        "layers": ["price_tech", "vol_sentiment"],
        "algorithm": "sac",
    },
    "L3_macro": {
        "label": "L3 Macro Extended",
        "symbols": ["AAPL"],
        "layers": ["price_tech", "vol_sentiment", "macro"],
        "algorithm": "sac",
    },
    "L4_fundamental": {
        "label": "L4 Fundamental Extended",
        "symbols": ["AAPL"],
        "layers": ["price_tech", "vol_sentiment", "macro", "fundamental"],
        "algorithm": "sac",
    },
    "L5_house_esg": {
        "label": "L5 House ESG",
        "symbols": ["AAPL"],
        "layers": ["price_tech", "vol_sentiment", "macro", "fundamental", "house_esg"],
        "algorithm": "sac",
    },
    "L6_multistock_general": {
        "label": "L6 Multi-Stock General Agent",
        "symbols": ["AAPL", "MSFT", "NVDA", "TSLA", "JPM", "NEE"],
        "layers": ["price_tech", "vol_sentiment", "macro", "fundamental", "house_esg", "multistock"],
        "algorithm": "hybrid_frontier",
    },
}

EXPERIMENT_PERIOD_2022_2025 = {
    "train": ("2022-01-01", "2023-12-31"),
    "validation": ("2024-01-01", "2024-12-31"),
    "test": ("2025-01-01", "2025-12-31"),
}


class QuantRLService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.artifact_store = get_artifact_store()
        self.repo = get_run_repository()
        self.recorder = ExperimentRecorder(self.settings.experiment_root)
        self.market_data = MarketDataGateway()
        self.data_sources = self._build_data_sources()
        self.esg_scorer = self._build_esg_scorer()

    def prepare_dataframe(
        self,
        dataset_path: str,
        use_demo_if_missing: bool = True,
        *,
        experiment_group: str | None = None,
        formula_mode: str | None = None,
    ) -> pd.DataFrame:
        path = self._resolve_dataset_file(Path(dataset_path))
        if path.exists():
            df = load_market_data(path)
        elif use_demo_if_missing:
            self.generate_demo_dataset(path)
            df = load_market_data(path)
        else:
            raise FileNotFoundError(dataset_path)
        df = add_technical_features(df)
        df = self._apply_formula_frame_overrides(df, formula_mode)
        return self._apply_experiment_frame_overrides(df, experiment_group)

    def build_env(self, df: pd.DataFrame, action_type: str = "discrete", *, experiment_group: str | None = None) -> TradingEnv:
        builder = ObservationBuilder(feature_columns=default_feature_columns(df))
        return TradingEnv(
            df,
            observation_builder=builder,
            env_cfg=TradingEnvConfig(action_type=action_type),
            reward_cfg=self._reward_config_for_group(experiment_group),
        )

    def generate_demo_dataset(
        self,
        target_path: str | Path = "storage/quant/demo/market.csv",
        *,
        seed: int = 42,
        length: int = 1500,
    ) -> dict:
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame = self._enrich_market_frame(
            generate_synthetic_ohlcv(n=length, seed=seed),
            symbol="DEMO",
            profile=self._fallback_symbol_profile("DEMO"),
        )
        frame.to_csv(target, index=False)

        manifest = {
            "dataset_name": target.parent.name,
            "mode": "demo",
            "primary_symbol": "DEMO",
            "rows": int(len(frame)),
            "dataset_path": str(target),
            "lineage": [
                "synthetic_ohlcv",
                "quant_rl.analysis.features",
                "gateway.quant.market_data-compatible schema",
            ],
        }
        manifest_path = self.recorder.record_dataset_manifest(manifest, name="demo/manifest.demo.json")
        return {
            "dataset_path": str(target),
            "rows": int(len(frame)),
            "manifest_path": manifest_path,
        }

    def build_market_dataset(
        self,
        symbols: list[str] | None = None,
        *,
        dataset_name: str | None = None,
        limit: int = 240,
        force_refresh: bool = False,
        include_esg: bool = True,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        selected_symbols = [item.upper().strip() for item in (symbols or self.default_symbols()) if str(item).strip()]
        if not selected_symbols:
            raise ValueError("At least one symbol is required to build an RL dataset")

        dataset_name = (dataset_name or f"market-pack-{uuid4().hex[:8]}").strip()
        dataset_dir = self.settings.storage_dir / "datasets" / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)

        symbol_payloads: list[dict] = []
        merged_frames: list[pd.DataFrame] = []
        for symbol in selected_symbols:
            bars_result = self.market_data.get_daily_bars(symbol, limit=max(60, int(limit)), force_refresh=force_refresh)
            bars_frame = self._filter_market_period(bars_result.bars, start_date=start_date, end_date=end_date)
            profile = self._load_symbol_profile(symbol) if include_esg else self._fallback_symbol_profile(symbol)
            frame = self._enrich_market_frame(bars_frame, symbol=symbol, profile=profile)
            frame["provider"] = bars_result.provider
            if not include_esg:
                frame = self._drop_esg_columns(frame)
            symbol_path = dataset_dir / f"{symbol}.csv"
            frame.to_csv(symbol_path, index=False)
            merged_frames.append(frame.assign(symbol=symbol))
            symbol_payloads.append(
                {
                    "symbol": symbol,
                    "provider": bars_result.provider,
                    "cache_hit": bool(bars_result.cache_hit),
                    "rows": int(len(frame)),
                    "dataset_path": str(symbol_path),
                    "start": str(frame["timestamp"].iloc[0]) if not frame.empty else None,
                    "end": str(frame["timestamp"].iloc[-1]) if not frame.empty else None,
                    "esg_score": round(
                        float(frame["house_score_v2_1"].iloc[-1] if "house_score_v2_1" in frame else frame["house_score_v2"].iloc[-1] if "house_score_v2" in frame else frame["house_score"].iloc[-1] if "house_score" in frame else frame["esg_score"].iloc[-1]) * 100,
                        2,
                    )
                    if (("house_score_v2_1" in frame) or ("house_score_v2" in frame) or ("house_score" in frame) or ("esg_score" in frame)) and not frame.empty else None,
                }
            )

        merged_path = dataset_dir / "merged_market.csv"
        pd.concat(merged_frames, ignore_index=True).to_csv(merged_path, index=False)

        manifest = {
            "dataset_name": dataset_name,
            "mode": "market_data_pack",
            "primary_symbol": selected_symbols[0],
            "primary_dataset_path": symbol_payloads[0]["dataset_path"],
            "merged_dataset_path": str(merged_path),
            "symbols": symbol_payloads,
            "limit": int(limit),
            "start_date": start_date,
            "end_date": end_date,
            "experiment_period": EXPERIMENT_PERIOD_2022_2025,
            "force_refresh": bool(force_refresh),
            "include_esg": bool(include_esg),
            "market_data_status": self.market_data.status(),
            "lineage": [
                "gateway.quant.market_data.MarketDataGateway",
                "gateway.scheduler.data_sources.DataSourceManager",
                "gateway.agents.esg_scorer.ESGScoringFramework",
                "quant_rl.analysis.features",
            ],
        }
        manifest_path = dataset_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        recorder_manifest_path = self.recorder.record_dataset_manifest(
            manifest,
            name=f"{dataset_name}/manifest.json",
        )

        return {
            "dataset_name": dataset_name,
            "dataset_dir": str(dataset_dir),
            "primary_symbol": selected_symbols[0],
            "primary_dataset_path": symbol_payloads[0]["dataset_path"],
            "merged_dataset_path": str(merged_path),
            "symbols": symbol_payloads,
            "manifest_path": str(manifest_path),
            "recorder_manifest_path": recorder_manifest_path,
        }

    def train(
        self,
        algorithm: str,
        dataset_path: str,
        action_type: str = "discrete",
        episodes: int = 50,
        total_steps: int = 500,
        use_demo_if_missing: bool = True,
        *,
        experiment_group: str | None = None,
        seed: int | None = None,
        notes: str | None = None,
        trainer_hparams: dict[str, Any] | None = None,
        formula_mode: str | None = None,
    ) -> dict:
        if seed is not None:
            set_seed(int(seed))

        df = self.prepare_dataframe(dataset_path, use_demo_if_missing, experiment_group=experiment_group, formula_mode=formula_mode)
        train_df, _, _ = time_split(df)
        env = self.build_env(train_df, action_type=action_type, experiment_group=experiment_group)

        algo = algorithm.lower().strip()
        run_id = f"{algo}-{uuid4().hex[:10]}"
        checkpoint_path = str(self.artifact_store.checkpoint_path(run_id))
        phase = self._phase_for_algorithm(algo)
        trainer_hparams = dict(trainer_hparams or {})
        learning_rate = float(trainer_hparams.get("learning_rate", 3e-4) or 3e-4)
        gamma = float(trainer_hparams.get("gamma", 0.99) or 0.99)
        batch_size = int(trainer_hparams.get("batch_size", 128) or 128)
        buffer_size = int(trainer_hparams.get("buffer_size", 100_000) or 100_000)
        learning_starts = int(trainer_hparams.get("learning_starts", 500) or 500)
        hidden_dim = self._hidden_dim_from_hparams(trainer_hparams, 256 if algo in {"sac", "hybrid_frontier"} else 128)

        if algo == "dqn":
            agent = DQNAgent(
                DQNConfig(
                    state_dim=env.state_dim,
                    action_dim=env.action_space.n,
                    gamma=gamma,
                    lr=learning_rate,
                    batch_size=batch_size,
                    buffer_cap=buffer_size,
                    start_learning=learning_starts,
                    hidden_dim=hidden_dim,
                )
            )
            summary = DQNTrainer(agent, env, run_id, checkpoint_path, self.artifact_store, self.repo).train(
                DQNTrainConfig(episodes=episodes)
            )
        elif algo == "ppo":
            continuous = action_type == "continuous"
            action_dim = 1 if continuous else env.action_space.n
            agent = PPOAgent(
                PPOConfig(
                    state_dim=env.state_dim,
                    action_dim=action_dim,
                    continuous=continuous,
                    gamma=gamma,
                    lr=learning_rate,
                    hidden_dim=hidden_dim,
                )
            )
            summary = PPOTrainer(agent, env, run_id, checkpoint_path, self.artifact_store, self.repo).train(
                PPOTrainConfig(total_steps=total_steps)
            )
        elif algo == "sac":
            agent = SACAgent(
                SACConfig(
                    state_dim=env.state_dim,
                    action_dim=1,
                    gamma=gamma,
                    actor_lr=learning_rate,
                    critic_lr=learning_rate,
                    alpha_lr=learning_rate,
                    batch_size=batch_size,
                    buffer_cap=buffer_size,
                    start_learning=learning_starts,
                    hidden_dim=hidden_dim,
                    tau=float(trainer_hparams.get("tau", 0.005) or 0.005),
                )
            )
            summary = SACTrainer(agent, env, run_id, checkpoint_path, self.artifact_store, self.repo).train(
                SACTrainConfig(total_steps=total_steps, warmup_steps=learning_starts)
            )
        elif algo == "cql":
            transitions = self._build_offline_transitions(train_df, continuous=False)
            agent = DQNAgent(
                DQNConfig(
                    state_dim=env.state_dim,
                    action_dim=env.action_space.n,
                    gamma=gamma,
                    lr=learning_rate,
                    batch_size=batch_size,
                    buffer_cap=buffer_size,
                    start_learning=learning_starts,
                    hidden_dim=hidden_dim,
                )
            )
            summary = OfflineDQNTrainer(agent, transitions, run_id, checkpoint_path, self.repo).train(
                OfflineCQLConfig(gradient_steps=total_steps)
            )
        elif algo == "iql":
            transitions = self._build_offline_transitions(train_df, continuous=True)
            learner = IQLLearner(IQLConfig(state_dim=env.state_dim, action_dim=1, hidden_dim=hidden_dim))
            summary = self._train_iql(learner, transitions, min(total_steps, 8))
            torch.save({"config": asdict(learner.config), "actor": learner.actor.state_dict()}, checkpoint_path)
        elif algo == "decision_transformer":
            transitions = self._build_offline_transitions(train_df, continuous=True)
            summary = self._train_dt(env.state_dim, transitions, checkpoint_path, min(total_steps, 8))
        elif algo == "world_model":
            transitions = self._build_offline_transitions(train_df, continuous=True)
            summary = self._train_wm(env.state_dim, transitions, checkpoint_path, min(total_steps, 8))
        elif algo == "hybrid_frontier":
            transitions = self._build_offline_transitions(train_df, continuous=True)
            learner = IQLLearner(IQLConfig(state_dim=env.state_dim, action_dim=1, hidden_dim=hidden_dim))
            iql_summary = self._train_iql(learner, transitions, min(total_steps, 4))
            dt_summary = self._train_dt(env.state_dim, transitions, checkpoint_path + ".dt", min(total_steps, 4))
            wm_summary = self._train_wm(env.state_dim, transitions, checkpoint_path + ".wm", min(total_steps, 4))
            torch.save({"config": asdict(learner.config), "actor": learner.actor.state_dict()}, checkpoint_path)
            summary = {
                "iql": iql_summary,
                "decision_transformer": dt_summary,
                "world_model": wm_summary,
            }
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        config = {
            "dataset_path": str(self._resolve_dataset_file(Path(dataset_path))),
            "action_type": action_type,
            "episodes": int(episodes),
            "total_steps": int(total_steps),
            "use_demo_if_missing": bool(use_demo_if_missing),
            "experiment_group": experiment_group,
            "seed": seed,
            "notes": notes or "",
            "trainer_hparams": trainer_hparams,
            "formula_mode": formula_mode,
        }
        artifacts = {"checkpoint_path": checkpoint_path}

        if experiment_group:
            recorder_artifacts = self.recorder.record_result(
                group=experiment_group,
                seed=seed,
                metrics=summary if isinstance(summary, dict) else {},
                checkpoint_path=checkpoint_path,
                notes=notes,
                training={
                    "final_train_reward": self._pick_numeric_metric(summary, ("episode_reward_mean", "reward_mean", "loss")),
                    "training_minutes": None,
                    "optuna_best_trial": trainer_hparams.get("best_trial_index"),
                    "optuna_best_val_sharpe": trainer_hparams.get("best_val_sharpe"),
                },
                artifacts=artifacts,
            )
            artifacts.update(recorder_artifacts)

        self.repo.save(
            RunInfo(
                run_id=run_id,
                algorithm=algo,
                phase=phase,
                status="trained",
                config=config,
                metrics=summary,
                artifacts=artifacts,
            )
        )
        return {
            "run_id": run_id,
            "algorithm": algo,
            "phase": phase,
            "checkpoint_path": checkpoint_path,
            "metrics": summary,
            "artifacts": artifacts,
            "config": config,
        }

    def backtest(
        self,
        algorithm: str,
        dataset_path: str,
        checkpoint_path: str | None = None,
        action_type: str = "discrete",
        *,
        experiment_group: str | None = None,
        seed: int | None = None,
        notes: str | None = None,
        formula_mode: str | None = None,
    ) -> dict:
        if seed is not None:
            set_seed(int(seed))

        algo = algorithm.lower().strip()
        resolved_checkpoint = self._resolve_checkpoint_path(algo, checkpoint_path)
        training_run = self._find_run_for_checkpoint(resolved_checkpoint) if resolved_checkpoint else None
        resolved_group = experiment_group or (training_run or {}).get("config", {}).get("experiment_group")
        df = self.prepare_dataframe(dataset_path, True, experiment_group=resolved_group, formula_mode=formula_mode)
        _, _, test_df = time_split(df)
        env = self.build_env(test_df, action_type=action_type, experiment_group=resolved_group)

        if algo == "buy_hold":
            from quant_rl.agents.buy_hold_agent import BuyHoldAgent

            agent = BuyHoldAgent(continuous=action_type == "continuous")
        elif algo == "rule_based":
            from quant_rl.agents.rule_based_agent import RuleBasedMomentumAgent

            agent = RuleBasedMomentumAgent(continuous=action_type == "continuous")
        elif algo == "random":
            from quant_rl.agents.random_agent import RandomAgent

            agent = RandomAgent(env.action_space)
        elif algo == "dqn":
            agent = DQNAgent.load(resolved_checkpoint)
        elif algo == "ppo":
            agent = PPOAgent.load(resolved_checkpoint)
        elif algo == "sac":
            agent = SACAgent.load(resolved_checkpoint)
        elif algo in {"iql", "hybrid_frontier"}:
            payload = torch.load(resolved_checkpoint, map_location="cpu")
            learner = IQLLearner(IQLConfig(**payload["config"]))
            learner.actor.load_state_dict(payload["actor"])
            agent = learner
        elif algo == "world_model":
            payload = torch.load(resolved_checkpoint, map_location="cpu")
            agent = WorldModelResearchAgent(WorldModelConfig(**payload["config"]))
            agent.model.load_state_dict(payload["model"])
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        result = BacktestEngine().run(agent, env, deterministic=True)
        history = env.history_frame()
        run_id = f"backtest-{uuid4().hex[:10]}"
        artifacts = build_backtest_reports(
            run_id=run_id,
            history=history,
            metrics=result.metrics,
            artifact_store=self.artifact_store,
        )

        resolved_seed = seed if seed is not None else (training_run or {}).get("config", {}).get("seed")
        if resolved_group:
            recorder_artifacts = self.recorder.record_result(
                group=resolved_group,
                seed=resolved_seed,
                metrics=result.metrics,
                history=history,
                checkpoint_path=resolved_checkpoint,
                notes=notes or (training_run or {}).get("config", {}).get("notes"),
                artifacts=artifacts,
            )
            artifacts.update(recorder_artifacts)

        config = {
            "dataset_path": str(self._resolve_dataset_file(Path(dataset_path))),
            "action_type": action_type,
            "checkpoint_path": resolved_checkpoint,
            "experiment_group": resolved_group,
            "seed": resolved_seed,
            "notes": notes or "",
        }
        self.repo.save(
            RunInfo(
                run_id=run_id,
                algorithm=algo,
                phase="evaluation_backtest",
                status="backtested",
                config=config,
                metrics=result.metrics,
                artifacts=artifacts,
            )
        )
        return {
            "run_id": run_id,
            "metrics": result.metrics,
            "artifacts": artifacts,
            "config": config,
        }

    def overview(self) -> dict:
        runs = self.repo.list_runs()
        protocol = self.recorder.protocol()
        latest_dataset = self._latest_dataset_descriptor(runs)
        latest_checkpoint = self._latest_checkpoint_descriptor(runs)
        latest_report = self._latest_report_descriptor(runs)
        artifact_health = {
            "dataset_ready": bool(latest_dataset.get("exists")),
            "checkpoint_ready": bool(latest_checkpoint.get("exists")),
            "report_ready": bool(latest_report.get("exists")),
        }
        remote_sync_status = {
            "status": "ready" if any(artifact_health.values()) else "awaiting_remote_artifact",
            "missing": [name for name, ready in artifact_health.items() if not ready],
        }
        return {
            "stack": {
                "foundation": ["double/dueling DQN baseline", "PPO", "SAC"],
                "production": ["offline CQL/IQL", "risk shield", "walk-forward validation", "paper trading handoff"],
                "frontier": [
                    "Decision Transformer",
                    "Dreamer/TD-MPC-inspired world model lane",
                    "uncertainty ensemble",
                    "hybrid offline-to-online training",
                ],
            },
            "endpoints": [
                "/api/v1/quant/rl/overview",
                "/api/v1/quant/rl/datasets/build",
                "/api/v1/quant/rl/recipes/build",
                "/api/v1/quant/rl/search",
                "/api/v1/quant/rl/train",
                "/api/v1/quant/rl/backtest",
                "/api/v1/quant/rl/runs",
                "/app/#/rl-lab",
            ],
            "runs": runs,
            "protocol": protocol,
            "output_status": self.recorder.output_status(),
            "storage": {
                "storage_dir": str(self.settings.storage_dir),
                "sqlite_db_path": str(self.settings.sqlite_db_path),
                "experiment_root": str(self.settings.experiment_root),
                "checkpoints_dir": str(self.settings.checkpoints_dir),
                "reports_dir": str(self.settings.reports_dir),
                "r2_enabled": bool(self.settings.r2_bucket and self.settings.r2_endpoint_url),
                "supabase_enabled": bool(self.settings.supabase_url and self.settings.supabase_key),
            },
            "services": {
                "market_data": self.market_data.status(),
                "alpha_vantage_ready": bool(self.data_sources and self.data_sources.source_status().get("alpha_vantage")),
                "alpaca_ready": bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_API_SECRET")),
                "esg_scoring_ready": self.esg_scorer is not None,
            },
            "latest_dataset": latest_dataset,
            "latest_checkpoint": latest_checkpoint,
            "latest_report": latest_report,
            "artifact_health": artifact_health,
            "remote_sync_status": remote_sync_status,
            "experiment_groups": [
                {
                    "key": key,
                    "label": value["label"],
                    "family": value["family"],
                    "algorithm": value["algorithm"],
                    "seeds": value["seeds"],
                }
                for key, value in EXPERIMENT_GROUPS.items()
            ],
            "default_symbols": self.default_symbols(),
            "recipes": [
                {
                    "key": key,
                    "label": value["label"],
                    "symbols": value["symbols"],
                    "layers": value["layers"],
                    "algorithm": value["algorithm"],
                }
                for key, value in RECIPE_PRESETS.items()
            ],
            "paper_execution_bridge": {
                "route": "/app/#/execution",
                "api": "/api/v1/quant/execution/run",
                "note": "RL lab uses the main quant execution stack for Alpaca paper routing.",
            },
        }

    @staticmethod
    def _artifact_descriptor(path: str | Path | None, *, label: str) -> dict[str, object]:
        if not path:
            return {"label": label, "path": "", "exists": False, "status": "missing"}
        artifact = Path(path)
        exists = artifact.exists()
        return {
            "label": label,
            "path": str(artifact),
            "exists": exists,
            "status": "ready" if exists else "missing",
            "modified_at": artifact.stat().st_mtime if exists else None,
        }

    def _latest_existing_file(self, patterns: list[str]) -> Path | None:
        matches: list[Path] = []
        for pattern in patterns:
            matches.extend(self.settings.storage_dir.glob(pattern))
            matches.extend(self.settings.experiment_root.glob(pattern))
        files = [match for match in matches if match.is_file()]
        if not files:
            return None
        files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        return files[0]

    def _latest_dataset_descriptor(self, runs: list[dict]) -> dict[str, object]:
        for run in runs:
            config = run.get("config") or {}
            dataset_path = config.get("dataset_path")
            if dataset_path:
                descriptor = self._artifact_descriptor(dataset_path, label="dataset")
                if descriptor["exists"]:
                    return descriptor
        latest = self._latest_existing_file(["datasets/**/*.csv", "quant/**/*.csv", "demo/*.csv"])
        return self._artifact_descriptor(latest, label="dataset")

    def _latest_checkpoint_descriptor(self, runs: list[dict]) -> dict[str, object]:
        for run in runs:
            artifacts = run.get("artifacts") or {}
            checkpoint_path = artifacts.get("checkpoint_path") or artifacts.get("checkpoint_uri")
            if checkpoint_path:
                descriptor = self._artifact_descriptor(checkpoint_path, label="checkpoint")
                if descriptor["exists"]:
                    return descriptor
        latest = self._latest_existing_file(["checkpoints/**/*", "**/*.pt", "**/*.pth", "**/*.ckpt"])
        return self._artifact_descriptor(latest, label="checkpoint")

    def _latest_report_descriptor(self, runs: list[dict]) -> dict[str, object]:
        for run in runs:
            artifacts = run.get("artifacts") or {}
            report_path = artifacts.get("report_path") or artifacts.get("workbook_path") or artifacts.get("metrics_path")
            if report_path:
                descriptor = self._artifact_descriptor(report_path, label="report")
                if descriptor["exists"]:
                    return descriptor
        latest = self._latest_existing_file(["reports/**/*", "**/*.xlsx", "**/*.json"])
        return self._artifact_descriptor(latest, label="report")

    def list_runs(self) -> list[dict]:
        return self.repo.list_runs()

    @staticmethod
    def default_symbols() -> list[str]:
        ordered: list[str] = []
        for values in MANUAL_STOCK_UNIVERSE.values():
            ordered.extend(values)
        return ordered

    def recipe_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "label": value["label"],
                "symbols": list(value["symbols"]),
                "layers": list(value["layers"]),
                "algorithm": value["algorithm"],
            }
            for key, value in RECIPE_PRESETS.items()
        ]

    @staticmethod
    def _recipe_profile_seed(symbol: str) -> int:
        return sum(ord(char) for char in symbol.upper())

    def _apply_recipe_layers_to_frame(self, frame: pd.DataFrame, *, symbol: str, profile: dict, layers: list[str]) -> pd.DataFrame:
        enriched = frame.copy()
        seed = self._recipe_profile_seed(symbol)
        phase = (seed % 23) / 7.0
        index = np.arange(len(enriched), dtype=float)

        if "vol_sentiment" in layers:
            enriched["put_call_ratio"] = 0.86 + np.sin(index / 18.0 + phase) * 0.08
        else:
            enriched = enriched.drop(columns=["put_call_ratio"], errors="ignore")

        if "macro" in layers:
            enriched["cpi_yoy"] = 0.024 + np.cos(index / 55.0 + phase) * 0.003
            enriched["fed_funds_rate"] = 0.043 + np.sin(index / 61.0 + phase) * 0.0025
        else:
            enriched = enriched.drop(columns=["cpi_yoy", "fed_funds_rate"], errors="ignore")

        if "fundamental" in layers:
            pe_anchor = float(profile.get("pe_ratio") or (18.0 + (seed % 9)))
            eps_anchor = float(profile.get("eps") or (4.5 + (seed % 5) * 0.35))
            revenue_growth = float(profile.get("revenue_growth") or (0.08 + (seed % 7) * 0.01))
            cashflow_yield = float(profile.get("cashflow_yield") or (0.03 + (seed % 5) * 0.004))
            enriched["pe_ratio"] = pe_anchor + np.sin(index / 120.0 + phase) * 0.35
            enriched["eps"] = eps_anchor + np.cos(index / 90.0 + phase) * 0.08
            enriched["revenue_growth"] = revenue_growth + np.sin(index / 110.0 + phase) * 0.004
            enriched["cashflow_yield"] = cashflow_yield + np.cos(index / 95.0 + phase) * 0.002
        else:
            enriched = enriched.drop(columns=["pe_ratio", "eps", "revenue_growth", "cashflow_yield"], errors="ignore")

        if "house_esg" not in layers:
            enriched = enriched.drop(
                columns=[
                    "house_score",
                    "house_score_v2",
                    "house_score_v2_1",
                    "esg_level",
                    "esg_score",
                    "esg_delta",
                    "esg_delta_v2_1",
                    "esg_confidence",
                    "esg_staleness_days",
                    "esg_effective_date",
                    "esg_missing_flag",
                    "sector_relative_esg",
                    "e_score",
                    "s_score",
                    "g_score",
                ],
                errors="ignore",
            )

        return enriched

    def build_recipe_dataset(
        self,
        recipe_key: str,
        *,
        dataset_name: str | None = None,
        limit: int = 240,
        force_refresh: bool = False,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if recipe_key not in RECIPE_PRESETS:
            raise ValueError(f"Unknown recipe_key: {recipe_key}")

        recipe = RECIPE_PRESETS[recipe_key]
        selected_symbols = [item.upper() for item in (symbols or recipe["symbols"])]
        payload = self.build_market_dataset(
            selected_symbols,
            dataset_name=dataset_name or recipe_key.lower(),
            limit=limit,
            force_refresh=force_refresh,
            include_esg="house_esg" in recipe["layers"],
            start_date=start_date,
            end_date=end_date,
        )

        for symbol_payload in payload["symbols"]:
            file_path = Path(symbol_payload["dataset_path"])
            frame = pd.read_csv(file_path)
            profile = self._load_symbol_profile(symbol_payload["symbol"]) if "house_esg" in recipe["layers"] else self._fallback_symbol_profile(symbol_payload["symbol"])
            frame = self._apply_recipe_layers_to_frame(frame, symbol=symbol_payload["symbol"], profile=profile, layers=recipe["layers"])
            frame.to_csv(file_path, index=False)

        merged_path = Path(payload["merged_dataset_path"])
        merged_frame = pd.read_csv(merged_path)
        updated_frames = []
        for symbol in sorted(set(merged_frame["symbol"].astype(str).str.upper())):
            profile = self._load_symbol_profile(symbol) if "house_esg" in recipe["layers"] else self._fallback_symbol_profile(symbol)
            updated_frames.append(
                self._apply_recipe_layers_to_frame(
                    merged_frame.loc[merged_frame["symbol"].astype(str).str.upper() == symbol].copy(),
                    symbol=symbol,
                    profile=profile,
                    layers=recipe["layers"],
                )
            )
        pd.concat(updated_frames, ignore_index=True).to_csv(merged_path, index=False)

        payload["recipe"] = {
            "key": recipe_key,
            "label": recipe["label"],
            "layers": list(recipe["layers"]),
            "algorithm": recipe["algorithm"],
        }
        payload["experiment_period"] = EXPERIMENT_PERIOD_2022_2025
        return payload

    def search_recipe(
        self,
        recipe_key: str,
        *,
        dataset_path: str | None = None,
        trials: int = 5,
        quick_steps: int = 120,
        action_type: str | None = None,
        seed: int = 42,
    ) -> dict[str, Any]:
        if recipe_key not in RECIPE_PRESETS:
            raise ValueError(f"Unknown recipe_key: {recipe_key}")
        recipe = RECIPE_PRESETS[recipe_key]
        if not dataset_path:
            dataset_manifest = self.build_recipe_dataset(recipe_key, dataset_name=f"{recipe_key.lower()}-search")
            dataset_path = dataset_manifest["merged_dataset_path"]

        algorithm = str(recipe["algorithm"])
        action_type = action_type or ("discrete" if algorithm in {"dqn", "cql"} else "continuous")
        trials_payload: list[dict[str, Any]] = []

        for index, params in enumerate(self._search_candidates(algorithm, trials)):
            tagged_params = dict(params)
            tagged_params["best_trial_index"] = index
            train_result = self.train(
                algorithm,
                dataset_path,
                action_type=action_type,
                episodes=max(10, quick_steps // 6),
                total_steps=quick_steps,
                use_demo_if_missing=False,
                experiment_group=None,
                seed=seed + index,
                notes=f"recipe_search={recipe_key}; trial={index}",
                trainer_hparams=tagged_params,
            )
            backtest_result = self.backtest(
                algorithm,
                dataset_path,
                checkpoint_path=train_result.get("checkpoint_path"),
                action_type=action_type,
                experiment_group=None,
                seed=seed + index,
                notes=f"recipe_search={recipe_key}; trial={index}",
            )
            sharpe = float(backtest_result.get("metrics", {}).get("sharpe", 0.0) or 0.0)
            max_drawdown = abs(float(backtest_result.get("metrics", {}).get("max_drawdown", 0.0) or 0.0))
            objective = sharpe - max_drawdown * 0.35
            trials_payload.append(
                {
                    "trial_index": index,
                    "params": params,
                    "train_run_id": train_result["run_id"],
                    "backtest_run_id": backtest_result["run_id"],
                    "sharpe": sharpe,
                    "max_drawdown": max_drawdown,
                    "objective": objective,
                    "checkpoint_path": train_result.get("checkpoint_path"),
                }
            )

        trials_payload.sort(key=lambda item: item["objective"], reverse=True)
        best = trials_payload[0]
        best_params = dict(best["params"])
        best_params["best_trial_index"] = int(best["trial_index"])
        best_params["best_val_sharpe"] = float(best["sharpe"])
        return {
            "recipe_key": recipe_key,
            "label": recipe["label"],
            "algorithm": algorithm,
            "dataset_path": dataset_path,
            "search_backend": "grid_fallback",
            "best_trial": best["trial_index"],
            "best_params": best_params,
            "best_val_sharpe": best["sharpe"],
            "trials": trials_payload,
        }

    def _resolve_dataset_file(self, path: Path) -> Path:
        if path.exists() and path.is_dir():
            preferred = [path / "merged_market.csv", path / "market.csv"]
            preferred.extend(sorted(path.glob("*.csv")))
            preferred.extend(sorted(path.rglob("*.csv")))
            for candidate in preferred:
                if candidate.exists():
                    return candidate
        return path

    @staticmethod
    def _phase_for_algorithm(algo: str) -> str:
        mapping = {
            "dqn": "phase_01_discrete_dqn",
            "ppo": "phase_02_policy_gradient",
            "sac": "phase_02_continuous_control",
            "cql": "phase_03_offline_rl",
            "iql": "phase_03_offline_iql",
            "decision_transformer": "phase_04_sequence_policy",
            "world_model": "phase_05_world_model_research",
            "hybrid_frontier": "phase_06_hybrid_frontier",
        }
        return mapping.get(algo, "phase_unknown")

    @staticmethod
    def _hidden_dim_from_hparams(trainer_hparams: dict[str, Any] | None, default: int) -> int:
        if not trainer_hparams:
            return default
        value = trainer_hparams.get("hidden_dim")
        if value is None:
            hidden_dims = trainer_hparams.get("hidden_dims")
            if isinstance(hidden_dims, (list, tuple)) and hidden_dims:
                value = hidden_dims[0]
        try:
            return int(value) if value is not None else int(default)
        except Exception:
            return int(default)

    @staticmethod
    def _search_candidates(algorithm: str, trials: int) -> list[dict[str, Any]]:
        base_grid = [
            {"learning_rate": 1e-4, "batch_size": 128, "buffer_size": 50_000, "learning_starts": 200, "hidden_dims": [128], "gamma": 0.99},
            {"learning_rate": 3e-4, "batch_size": 128, "buffer_size": 100_000, "learning_starts": 500, "hidden_dims": [256], "gamma": 0.99},
            {"learning_rate": 5e-4, "batch_size": 256, "buffer_size": 100_000, "learning_starts": 800, "hidden_dims": [256], "gamma": 0.985},
            {"learning_rate": 8e-4, "batch_size": 256, "buffer_size": 120_000, "learning_starts": 1000, "hidden_dims": [192], "gamma": 0.995},
            {"learning_rate": 2e-4, "batch_size": 512, "buffer_size": 80_000, "learning_starts": 400, "hidden_dims": [128], "gamma": 0.99},
        ]
        if algorithm == "hybrid_frontier":
            for item in base_grid:
                item["hidden_dims"] = [256]
        return base_grid[: max(1, min(trials, len(base_grid)))]

    @staticmethod
    def _apply_formula_frame_overrides(df: pd.DataFrame, formula_mode: str | None) -> pd.DataFrame:
        mode = str(formula_mode or "").strip().lower()
        if mode not in {"v2", "v2_1", "v2.1", "calibrated"}:
            return df
        frame = df.copy()
        if mode == "v2":
            return frame.drop(columns=["house_score_v2_1", "esg_delta_v2_1", "sector_relative_esg"], errors="ignore")

        if "house_score_v2_1" in frame.columns:
            frame["house_score_v2"] = frame["house_score_v2_1"]
            frame["house_score"] = frame["house_score_v2_1"]
            frame["esg_score"] = frame["house_score_v2_1"]
            frame["esg_level"] = frame["house_score_v2_1"]
        if "esg_delta_v2_1" in frame.columns:
            frame["esg_delta"] = frame["esg_delta_v2_1"]
        return frame

    @staticmethod
    def _apply_experiment_frame_overrides(df: pd.DataFrame, experiment_group: str | None) -> pd.DataFrame:
        if not experiment_group:
            return df
        frame = df.copy()
        esg_columns = [
            "house_score",
            "house_score_v2",
            "house_score_v2_1",
            "esg_level",
            "esg_score",
            "esg_delta",
            "esg_delta_v2_1",
            "esg_confidence",
            "esg_staleness_days",
            "esg_effective_date",
            "esg_missing_flag",
            "sector_relative_esg",
            "e_score",
            "s_score",
            "g_score",
        ]
        regime_columns = ["vix", "us10y_yield", "credit_spread"]

        if experiment_group in {"B3_sac_noesg", "6a_no_esg_obs"}:
            frame = frame.drop(columns=[column for column in esg_columns if column in frame.columns], errors="ignore")
        if experiment_group == "6c_no_regime":
            frame = frame.drop(columns=[column for column in regime_columns if column in frame.columns], errors="ignore")
        return frame

    @staticmethod
    def _drop_esg_columns(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.drop(
            columns=[
                "house_score",
                "house_score_v2",
                "house_score_v2_1",
                "esg_level",
                "esg_score",
                "esg_delta",
                "esg_delta_v2_1",
                "esg_confidence",
                "esg_staleness_days",
                "esg_effective_date",
                "esg_missing_flag",
                "sector_relative_esg",
                "e_score",
                "s_score",
                "g_score",
            ],
            errors="ignore",
        )

    @staticmethod
    def _reward_config_for_group(experiment_group: str | None) -> RewardConfig:
        if experiment_group in {"B3_sac_noesg", "6b_no_esg_reward"}:
            return RewardConfig(esg_bonus_scale=0.0)
        if experiment_group in {"B4_sac_esg", "OURS_full", "6a_no_esg_obs", "6c_no_regime"}:
            return RewardConfig(esg_bonus_scale=0.02)
        return RewardConfig(esg_bonus_scale=0.0)

    def _resolve_checkpoint_path(self, algo: str, checkpoint_path: str | None) -> str | None:
        if checkpoint_path:
            return str(checkpoint_path)
        if algo in {"buy_hold", "rule_based", "random"}:
            return None

        for run in self.repo.list_runs():
            if str(run.get("algorithm")).lower() != algo:
                continue
            candidate = str((run.get("artifacts") or {}).get("checkpoint_path") or "").strip()
            if candidate and Path(candidate).exists():
                return candidate
        raise FileNotFoundError(f"No checkpoint found for algorithm '{algo}'. Train a run first or provide checkpoint_path.")

    def _find_run_for_checkpoint(self, checkpoint_path: str | None) -> dict | None:
        if not checkpoint_path:
            return None
        normalized = str(Path(checkpoint_path))
        for run in self.repo.list_runs():
            candidate = str((run.get("artifacts") or {}).get("checkpoint_path") or "")
            if candidate and str(Path(candidate)) == normalized:
                return run
        return None

    @staticmethod
    def _pick_numeric_metric(payload: dict, keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @staticmethod
    def _build_data_sources() -> DataSourceManager | None:
        try:
            return DataSourceManager()
        except Exception:
            return None

    @staticmethod
    def _build_esg_scorer():
        if ESGScoringFramework is None:
            return None
        try:
            return ESGScoringFramework()
        except Exception:
            return None

    def _load_symbol_profile(self, symbol: str) -> dict:
        local_profile = self._load_local_esg_profile(symbol)
        if local_profile is not None:
            return local_profile
        fallback = self._fallback_symbol_profile(symbol)
        if self.data_sources is None:
            return fallback

        try:
            company = self.data_sources.fetch_company_data(symbol, ticker=symbol)
            company_payload = company.model_dump(mode="json") if hasattr(company, "model_dump") else dict(company)
        except Exception:
            return fallback

        if self.esg_scorer is None:
            return fallback

        try:
            report = self.esg_scorer.score_esg(symbol, company_payload)
            return {
                "overall_score": float(report.overall_score),
                "house_score": float(report.house_score or report.overall_score),
                "house_score_v2": float(report.house_score or report.overall_score),
                "house_score_v2_1": float(report.house_score or report.overall_score),
                "house_grade": str(report.house_grade or ""),
                "e_score": float(report.e_scores.overall_score),
                "s_score": float(report.s_scores.overall_score),
                "g_score": float(report.g_scores.overall_score),
                "esg_confidence": float(report.disclosure_confidence or 0.72),
                "evidence_count": len(list(company_payload.get("data_sources") or [])),
                "data_sources": list(company_payload.get("data_sources") or []),
                "house_explanation": str(report.house_explanation or ""),
            }
        except Exception:
            return fallback

    @staticmethod
    def _fallback_symbol_profile(symbol: str) -> dict:
        seed = sum(ord(char) for char in symbol.upper())
        base = 58 + (seed % 20)
        e_score = min(90.0, base + ((seed // 3) % 7))
        s_score = min(90.0, base - 2 + ((seed // 5) % 9))
        g_score = min(90.0, base + 1 + ((seed // 7) % 8))
        overall = round(e_score * 0.35 + s_score * 0.35 + g_score * 0.30, 2)
        return {
            "overall_score": overall,
            "house_score": overall,
            "house_score_v2": overall,
            "house_score_v2_1": overall,
            "house_grade": "BBB",
            "e_score": e_score,
            "s_score": s_score,
            "g_score": g_score,
            "esg_confidence": 0.42,
            "evidence_count": 0,
            "sector_relative_esg": 0.0,
            "data_sources": [],
            "house_explanation": f"{symbol} fallback house score mirrors overall ESG score in offline mode.",
        }

    @staticmethod
    def _filter_market_period(frame: pd.DataFrame, *, start_date: str | None, end_date: str | None) -> pd.DataFrame:
        if frame.empty or not (start_date or end_date):
            return frame
        filtered = frame.copy()
        filtered["timestamp"] = pd.to_datetime(filtered["timestamp"], utc=True)
        if start_date:
            start = pd.Timestamp(start_date, tz="UTC")
            filtered = filtered.loc[filtered["timestamp"] >= start]
        if end_date:
            end = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            filtered = filtered.loc[filtered["timestamp"] <= end]
        return filtered.reset_index(drop=True)

    @staticmethod
    def _load_local_esg_profile(symbol: str) -> dict | None:
        score_path = Path("storage/esg_corpus/house_scores_v2.json")
        if not score_path.exists():
            return None
        try:
            rows = json.loads(score_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        symbol_rows = [
            row for row in rows
            if str(row.get("ticker", "")).upper() == symbol.upper()
        ]
        if not symbol_rows:
            return None
        usable_rows = [
            row for row in symbol_rows
            if float(row.get("coverage") or 0.0) > 0 and row.get("effective_date")
        ]
        latest = (usable_rows or symbol_rows)[-1]
        pillar = latest.get("pillar_breakdown") or {}
        return {
            "overall_score": float(latest.get("house_score") or 50.0),
            "house_score": float(latest.get("house_score") or 50.0),
            "house_score_v2": float(latest.get("house_score") or 50.0),
            "house_score_v2_1": float(latest.get("house_score_v2_1") or latest.get("house_score") or 50.0),
            "house_grade": str(latest.get("house_grade") or ""),
            "e_score": float(pillar.get("E", 50.0)),
            "s_score": float(pillar.get("S", 50.0)),
            "g_score": float(pillar.get("G", 50.0)),
            "esg_confidence": float(latest.get("disclosure_confidence") or 0.35),
            "evidence_count": int(latest.get("evidence_count") or 0),
            "sector_relative_esg": float(latest.get("sector_relative_esg") or 0.0),
            "data_sources": list(latest.get("explanation_sources") or latest.get("data_sources") or []),
            "house_explanation": str(latest.get("house_explanation") or ""),
            "score_timeseries": usable_rows,
        }

    @staticmethod
    def _enrich_market_frame(frame: pd.DataFrame, *, symbol: str, profile: dict) -> pd.DataFrame:
        enriched = frame.copy()
        enriched["timestamp"] = pd.to_datetime(enriched["timestamp"], utc=True)
        timeline = list(profile.get("score_timeseries") or [])
        if timeline:
            return QuantRLService._apply_esg_timeline(enriched, symbol=symbol, profile=profile, timeline=timeline)

        phase = (sum(ord(char) for char in symbol.upper()) % 17) / 5.0
        index = np.arange(len(enriched), dtype=float)

        if int(profile.get("evidence_count", 0) or 0) == 0:
            enriched["esg_score"] = 0.5
            enriched["house_score"] = 0.5
            enriched["house_score_v2"] = 0.5
            enriched["house_score_v2_1"] = 0.5
            enriched["esg_level"] = 0.5
            enriched["e_score"] = 0.5
            enriched["s_score"] = 0.5
            enriched["g_score"] = 0.5
            enriched["esg_delta"] = 0.0
            enriched["esg_delta_v2_1"] = 0.0
            enriched["esg_confidence"] = 0.0
            enriched["esg_staleness_days"] = 9999.0
            enriched["esg_effective_date"] = ""
            enriched["esg_missing_flag"] = 1.0
            enriched["sector_relative_esg"] = 0.0
            enriched["vix"] = 0.18 + 0.05 * np.sin(index / 19.0 + phase)
            enriched["us10y_yield"] = 0.035 + 0.004 * np.cos(index / 41.0 + phase)
            enriched["credit_spread"] = 0.012 + 0.003 * np.sin(index / 27.0 + phase / 2.0)
            return enriched

        base_overall = float(profile.get("house_score", profile.get("overall_score", 65.0))) / 100.0
        base_v2 = float(profile.get("house_score_v2", profile.get("house_score", profile.get("overall_score", 65.0)))) / 100.0
        base_v2_1 = float(profile.get("house_score_v2_1", profile.get("house_score_v2", profile.get("house_score", profile.get("overall_score", 65.0))))) / 100.0
        base_e = float(profile.get("e_score", 66.0)) / 100.0
        base_s = float(profile.get("s_score", 64.0)) / 100.0
        base_g = float(profile.get("g_score", 67.0)) / 100.0
        confidence = float(profile.get("esg_confidence", 0.72) or 0.72)

        enriched["esg_score"] = np.clip(base_overall + np.sin(index / 36.0 + phase) * 0.015, 0.0, 1.0)
        enriched["house_score"] = enriched["esg_score"]
        enriched["house_score_v2"] = np.clip(base_v2 + np.sin(index / 52.0 + phase) * 0.010, 0.0, 1.0)
        enriched["house_score_v2_1"] = np.clip(base_v2_1 + np.sin(index / 64.0 + phase) * 0.008, 0.0, 1.0)
        enriched["esg_level"] = enriched["house_score_v2_1"]
        enriched["e_score"] = np.clip(base_e + np.sin(index / 33.0 + phase) * 0.012, 0.0, 1.0)
        enriched["s_score"] = np.clip(base_s + np.cos(index / 40.0 + phase) * 0.01, 0.0, 1.0)
        enriched["g_score"] = np.clip(base_g + np.sin(index / 44.0 + phase / 2.0) * 0.008, 0.0, 1.0)
        enriched["esg_delta"] = enriched["house_score_v2"].diff().fillna(0.0)
        enriched["esg_delta_v2_1"] = enriched["house_score_v2_1"].diff().fillna(0.0)
        enriched["esg_confidence"] = np.clip(confidence, 0.0, 1.0)
        enriched["esg_staleness_days"] = np.minimum(index.astype(int), 730)
        enriched["esg_effective_date"] = str(profile.get("effective_date") or "")
        enriched["esg_missing_flag"] = 1.0 if int(profile.get("evidence_count", 0) or 0) == 0 else 0.0
        enriched["sector_relative_esg"] = float(profile.get("sector_relative_esg") or 0.0)
        enriched["vix"] = 0.18 + 0.05 * np.sin(index / 19.0 + phase)
        enriched["us10y_yield"] = 0.035 + 0.004 * np.cos(index / 41.0 + phase)
        enriched["credit_spread"] = 0.012 + 0.003 * np.sin(index / 27.0 + phase / 2.0)
        return enriched

    @staticmethod
    def _apply_esg_timeline(frame: pd.DataFrame, *, symbol: str, profile: dict, timeline: list[dict[str, Any]]) -> pd.DataFrame:
        enriched = frame.copy()
        enriched["timestamp"] = pd.to_datetime(enriched["timestamp"], utc=True)
        index = np.arange(len(enriched), dtype=float)
        phase = (sum(ord(char) for char in symbol.upper()) % 17) / 5.0

        parsed_rows: list[dict[str, Any]] = []
        for row in timeline:
            effective = pd.to_datetime(row.get("effective_date"), utc=True, errors="coerce")
            if pd.isna(effective):
                continue
            parsed_rows.append({**row, "_effective_ts": effective})
        parsed_rows.sort(key=lambda item: item["_effective_ts"])

        neutral = {
            "house_score": 0.5,
            "e_score": 0.5,
            "s_score": 0.5,
            "g_score": 0.5,
            "confidence": 0.0,
            "delta": 0.0,
        }

        house_values: list[float] = []
        house_v2_1_values: list[float] = []
        e_values: list[float] = []
        s_values: list[float] = []
        g_values: list[float] = []
        confidence_values: list[float] = []
        delta_values: list[float] = []
        delta_v2_1_values: list[float] = []
        sector_relative_values: list[float] = []
        staleness_values: list[float] = []
        effective_date_values: list[str] = []
        missing_values: list[float] = []
        current_idx = -1
        for ts in enriched["timestamp"]:
            while current_idx + 1 < len(parsed_rows) and parsed_rows[current_idx + 1]["_effective_ts"] <= ts:
                current_idx += 1
            if current_idx < 0:
                house_values.append(neutral["house_score"])
                house_v2_1_values.append(neutral["house_score"])
                e_values.append(neutral["e_score"])
                s_values.append(neutral["s_score"])
                g_values.append(neutral["g_score"])
                confidence_values.append(neutral["confidence"])
                delta_values.append(0.0)
                delta_v2_1_values.append(0.0)
                sector_relative_values.append(0.0)
                staleness_values.append(9999.0)
                effective_date_values.append("")
                missing_values.append(1.0)
                continue
            row = parsed_rows[current_idx]
            pillar = row.get("pillar_breakdown") or {}
            effective_ts = row["_effective_ts"]
            house_values.append(float(row.get("house_score") or 50.0) / 100.0)
            house_v2_1_values.append(float(row.get("house_score_v2_1") or row.get("house_score") or 50.0) / 100.0)
            e_values.append(float(pillar.get("E", 50.0)) / 100.0)
            s_values.append(float(pillar.get("S", 50.0)) / 100.0)
            g_values.append(float(pillar.get("G", 50.0)) / 100.0)
            confidence_values.append(float(row.get("disclosure_confidence") or row.get("confidence") or 0.35))
            delta_values.append(float(row.get("score_delta") or 0.0))
            delta_v2_1_values.append(float(row.get("score_delta_v2_1") or row.get("score_delta") or 0.0))
            sector_relative_values.append(float(row.get("sector_relative_esg") or 0.0))
            staleness_values.append(float(max(0, (ts.normalize() - effective_ts.normalize()).days)))
            effective_date_values.append(effective_ts.date().isoformat())
            missing_values.append(0.0)

        enriched["house_score_v2"] = np.clip(house_values, 0.0, 1.0)
        enriched["house_score_v2_1"] = np.clip(house_v2_1_values, 0.0, 1.0)
        enriched["house_score"] = enriched["house_score_v2"]
        enriched["esg_score"] = enriched["house_score_v2_1"]
        enriched["esg_level"] = enriched["house_score_v2_1"]
        enriched["e_score"] = np.clip(e_values, 0.0, 1.0)
        enriched["s_score"] = np.clip(s_values, 0.0, 1.0)
        enriched["g_score"] = np.clip(g_values, 0.0, 1.0)
        enriched["esg_delta"] = np.array(delta_values, dtype=float)
        enriched["esg_delta_v2_1"] = np.array(delta_v2_1_values, dtype=float)
        enriched["esg_confidence"] = np.clip(confidence_values, 0.0, 1.0)
        enriched["esg_staleness_days"] = np.array(staleness_values, dtype=float)
        enriched["esg_effective_date"] = effective_date_values
        enriched["esg_missing_flag"] = np.array(missing_values, dtype=float)
        enriched["sector_relative_esg"] = np.array(sector_relative_values, dtype=float)
        enriched["vix"] = 0.18 + 0.05 * np.sin(index / 19.0 + phase)
        enriched["us10y_yield"] = 0.035 + 0.004 * np.cos(index / 41.0 + phase)
        enriched["credit_spread"] = 0.012 + 0.003 * np.sin(index / 27.0 + phase / 2.0)
        return enriched

    def _build_offline_transitions(self, train_df: pd.DataFrame, continuous: bool = False):
        env = self.build_env(train_df, action_type="continuous" if continuous else "discrete")
        state, _ = env.reset()
        transitions = []
        done = False
        while not done:
            momentum = state[0]
            action = (
                float(np.clip(momentum * 5.0, -1.0, 1.0))
                if continuous
                else (2 if momentum > 0 else (0 if momentum < 0 else 1))
            )
            next_state, reward, terminated, truncated, _ = env.step(action)
            transitions.append(
                Transition(
                    state=state,
                    action=action,
                    reward=reward,
                    next_state=next_state,
                    done=float(terminated or truncated),
                )
            )
            state = next_state
            done = terminated or truncated
        return transitions

    def _train_iql(self, learner, transitions, total_steps):
        buf = ReplayBuffer(max(2000, len(transitions) + 1))
        for tr in transitions:
            buf.push(tr.state, np.array([tr.action], dtype=np.float32), tr.reward, tr.next_state, tr.done)
        logs = []
        for _ in range(total_steps):
            batch = buf.sample(min(16, len(buf)))
            logs.append(learner.update(batch))
        return {
            "steps": len(logs),
            **({key: float(np.mean([metric[key] for metric in logs])) for key in logs[0].keys()} if logs else {}),
        }

    def _train_dt(self, state_dim, transitions, checkpoint_path, total_steps):
        seq_len = 8
        trainer = DecisionTransformerTrainer(
            DecisionTransformerConfig(state_dim=state_dim, action_dim=1, seq_len=seq_len, hidden_dim=64, n_layers=1)
        )
        windows = []
        upper_bound = max(1, min(len(transitions) - seq_len, 32))
        for start in range(0, upper_bound):
            chunk = transitions[start : start + seq_len]
            if len(chunk) < seq_len:
                chunk = chunk + [chunk[-1]] * (seq_len - len(chunk))
            states = np.stack([tr.state for tr in chunk]).astype(np.float32)
            actions = np.array([[tr.action] for tr in chunk], dtype=np.float32)
            rewards = np.array([tr.reward for tr in chunk], dtype=np.float32)
            rtg = rewards[::-1].cumsum()[::-1].astype(np.float32)
            ts = np.arange(seq_len, dtype=np.int64)
            windows.append((states, actions, rtg, ts))
        logs = []
        for step in range(total_steps):
            states, actions, rtg, ts = windows[step % len(windows)]
            logs.append(trainer.update(states[None, ...], actions[None, ...], rtg[None, ...], ts[None, ...]))
        torch.save({"config": asdict(trainer.config), "state_dict": trainer.model.state_dict()}, checkpoint_path)
        return {"steps": len(logs), "loss": float(np.mean([metric["loss"] for metric in logs])) if logs else 0.0}

    def _train_wm(self, state_dim, transitions, checkpoint_path, total_steps):
        agent = WorldModelResearchAgent(WorldModelConfig(state_dim=state_dim, action_dim=1, hidden_dim=64, latent_dim=32))
        buf = ReplayBuffer(max(2000, len(transitions) + 1))
        for tr in transitions:
            buf.push(tr.state, np.array([tr.action], dtype=np.float32), tr.reward, tr.next_state, tr.done)
        logs = []
        for _ in range(total_steps):
            batch = buf.sample(min(16, len(buf)))
            logs.append(agent.update(batch))
        torch.save({"config": asdict(agent.config), "model": agent.model.state_dict()}, checkpoint_path)
        return {"steps": len(logs), "loss": float(np.mean([metric["loss"] for metric in logs])) if logs else 0.0}
