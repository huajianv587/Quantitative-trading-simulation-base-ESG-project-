from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
except Exception:
    gym = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.p2_decision import P2_STRATEGY_SNAPSHOT_COLUMNS

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "advanced_decision"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "ppo_policy"


def _load_frame(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


class StrategyRoutingEnv(gym.Env if gym is not None else object):
    def __init__(self, frame: pd.DataFrame, *, feature_names: list[str], arms: list[str]) -> None:
        from gymnasium import spaces

        self.feature_names = list(feature_names)
        self.arms = list(arms)
        self.dates = sorted(frame["date"].astype(str).unique().tolist())
        self.grouped = {
            date: group.copy().reset_index(drop=True)
            for date, group in frame.groupby(frame["date"].astype(str))
        }
        self.action_space = spaces.Discrete(len(self.arms))
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(len(self.feature_names),),
            dtype=np.float32,
        )
        self.index = 0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.index = 0
        observation = self._observation_for(self.dates[self.index])
        return observation, {}

    def step(self, action: int):
        current_date = self.dates[self.index]
        current_slice = self.grouped[current_date]
        action_index = max(0, min(len(self.arms) - 1, int(action)))
        arm_name = self.arms[action_index]
        chosen = current_slice[current_slice["arm"].astype(str) == arm_name]
        if chosen.empty:
            reward = float(current_slice["reward"].min())
        else:
            reward = float(chosen.iloc[0]["reward"])
        best_row = current_slice.sort_values("reward", ascending=False).iloc[0]
        info = {
            "date": current_date,
            "selected_arm": arm_name,
            "best_arm": str(best_row["arm"]),
            "reward": reward,
            "best_reward": float(best_row["reward"]),
        }
        self.index += 1
        terminated = self.index >= len(self.dates)
        if terminated:
            observation = np.zeros(len(self.feature_names), dtype=np.float32)
        else:
            observation = self._observation_for(self.dates[self.index])
        return observation, reward, terminated, False, info

    def _observation_for(self, date: str) -> np.ndarray:
        row = self.grouped[date].iloc[0]
        return row[self.feature_names].to_numpy(dtype=np.float32)


def _evaluate_policy(model, frame: pd.DataFrame, *, feature_names: list[str], arms: list[str]) -> dict[str, float]:
    env = StrategyRoutingEnv(frame, feature_names=feature_names, arms=arms)
    observation, _ = env.reset()
    rewards: list[float] = []
    action_matches: list[float] = []
    done = False
    while not done:
        action, _ = model.predict(observation, deterministic=True)
        observation, reward, terminated, truncated, info = env.step(int(action))
        done = bool(terminated or truncated)
        rewards.append(float(reward))
        action_matches.append(1.0 if str(info.get("selected_arm")) == str(info.get("best_arm")) else 0.0)
    if not rewards:
        return {"mean_reward": 0.0, "hit_rate": 0.0, "best_arm_match": 0.0}
    series = pd.Series(rewards, dtype="float64")
    return {
        "mean_reward": round(float(series.mean()), 6),
        "hit_rate": round(float((series > 0).mean()), 6),
        "best_arm_match": round(float(np.mean(action_matches)), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a PPO strategy-routing policy from advanced decision contexts.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "bandit_contexts_train.csv"), help="Training context csv.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "bandit_contexts_val.csv"), help="Validation context csv.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output checkpoint directory.")
    parser.add_argument("--total-timesteps", type=int, default=20000, help="Total PPO timesteps.")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="Learning rate.")
    parser.add_argument("--n-steps", type=int, default=512, help="Rollout length.")
    parser.add_argument("--batch-size", type=int, default=512, help="Batch size.")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor.")
    parser.add_argument("--gae-lambda", type=float, default=0.95, help="GAE lambda.")
    parser.add_argument("--ent-coef", type=float, default=0.01, help="Entropy regularization.")
    parser.add_argument("--vf-coef", type=float, default=0.5, help="Value loss coefficient.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--num-envs", type=int, default=1, help="Number of vectorized training env copies.")
    parser.add_argument("--dry-run", action="store_true", help="Validate data and emit a manifest without fitting.")
    args = parser.parse_args()

    train_frame = _load_frame(args.train_csv)
    val_frame = _load_frame(args.val_csv)
    arms = sorted(train_frame["arm"].astype(str).unique().tolist())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata: dict[str, object] = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "model_name": "ppo_strategy_router",
        "feature_names": list(P2_STRATEGY_SNAPSHOT_COLUMNS),
        "arms": list(arms),
        "train_rows": int(len(train_frame)),
        "val_rows": int(len(val_frame)),
        "total_timesteps": int(args.total_timesteps),
        "learning_rate": float(args.learning_rate),
        "n_steps": int(args.n_steps),
        "batch_size": int(args.batch_size),
        "gamma": float(args.gamma),
        "gae_lambda": float(args.gae_lambda),
        "ent_coef": float(args.ent_coef),
        "vf_coef": float(args.vf_coef),
        "num_envs": int(args.num_envs),
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output_dir": str(output_dir), **metadata}, ensure_ascii=False, indent=2))
        return 0

    if gym is None:
        raise SystemExit("gymnasium is required for PPO training. Install training/cloud_assets/requirements_cloud_extra.txt first.")

    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv
    except Exception as exc:
        raise SystemExit(f"stable-baselines3 is required for PPO training: {exc}") from exc

    def make_env():
        return StrategyRoutingEnv(
            train_frame,
            feature_names=list(P2_STRATEGY_SNAPSHOT_COLUMNS),
            arms=arms,
        )

    vec_env = DummyVecEnv([make_env for _ in range(max(1, int(args.num_envs)))])
    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        ent_coef=args.ent_coef,
        vf_coef=args.vf_coef,
        seed=args.seed,
        verbose=1,
    )
    model.learn(total_timesteps=args.total_timesteps, progress_bar=False)
    model_path = output_dir / "policy"
    model.save(str(model_path))

    validation = _evaluate_policy(
        model,
        val_frame,
        feature_names=list(P2_STRATEGY_SNAPSHOT_COLUMNS),
        arms=arms,
    )
    metadata["validation"] = validation
    metadata["policy_path"] = str(model_path.with_suffix(".zip"))
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **metadata}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
