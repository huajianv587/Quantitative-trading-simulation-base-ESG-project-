from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.infrastructure.settings import get_settings
from quant_rl.reporting.experiment_recorder import EXPERIMENT_GROUPS
from quant_rl.service.quant_service import QuantRLService


def _resolve_groups(raw: str) -> list[str]:
    if raw.strip().lower() == "all":
        return list(EXPERIMENT_GROUPS.keys())
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_seed_override(raw: str | None) -> list[int] | None:
    if raw is None or not raw.strip():
        return None
    return [int(item.strip()) for item in raw.replace(",", " ").split() if item.strip()]


def _action_type_for_algorithm(algorithm: str) -> str:
    return "discrete" if algorithm in {"buy_hold", "rule_based", "random", "dqn", "cql"} else "continuous"


def _namespace_root(namespace: str) -> Path:
    return ROOT / "storage" / "quant" / "rl-experiments" / namespace


def _sample_output_root(
    *,
    namespace: str,
    sample: str,
    formula_mode: str | None,
    sample_output_root: str | None,
) -> Path:
    if sample_output_root:
        return Path(sample_output_root)
    root = _namespace_root(namespace)
    if formula_mode:
        root = root / f"formula_{formula_mode}"
    if namespace == "paper-run":
        root = root / f"sample_{sample}"
    return root


def _default_protocol_file(namespace: str, sample: str) -> Path:
    return _namespace_root(namespace) / "protocol" / f"frozen_inputs_{sample}.json"


def _load_protocol(protocol_file: str | None, *, namespace: str, sample: str) -> tuple[dict[str, Any] | None, Path | None]:
    path = Path(protocol_file) if protocol_file else _default_protocol_file(namespace, sample)
    if not path.exists():
        return None, path
    return json.loads(path.read_text(encoding="utf-8")), path


def _normal_path(value: str | Path | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "/").strip().lower()


def _sha256_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gpu_telemetry() -> dict[str, Any]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    try:
        output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, timeout=10).strip()
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    rows = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 6:
            rows.append(
                {
                    "name": parts[0],
                    "memory_total_mb": parts[1],
                    "memory_used_mb": parts[2],
                    "utilization_gpu_pct": parts[3],
                    "temperature_c": parts[4],
                    "power_draw_w": parts[5],
                }
            )
    return {"available": bool(rows), "gpus": rows, "raw": output}


def _environment_snapshot(args: argparse.Namespace, dataset_sha256: str | None, protocol_file: Path | None) -> dict[str, Any]:
    return {
        "created_at": _utc_now(),
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": str(ROOT),
        "arguments": vars(args),
        "dataset_sha256": dataset_sha256,
        "protocol_file": str(protocol_file) if protocol_file else None,
        "env": {
            "CUDA_VISIBLE_DEVICES": os.getenv("CUDA_VISIBLE_DEVICES"),
            "QUANT_RL_EXPERIMENT_ROOT": os.getenv("QUANT_RL_EXPERIMENT_ROOT"),
        },
        "gpu": _gpu_telemetry(),
    }


def _run_dir(output_root: Path, group: str, seed: int | None) -> Path:
    path = output_root / "results" / group
    if seed is not None:
        path = path / f"seed{seed}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_complete(output_root: Path, group: str, seed: int | None) -> bool:
    run_dir = _run_dir(output_root, group, seed)
    status_path = run_dir / "run_status.json"
    if not ((run_dir / "metrics.json").exists() and (run_dir / "equity_curve.csv").exists() and status_path.exists()):
        return False
    try:
        status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
    except Exception:
        return False
    return status in {"completed", "skipped_existing"}


def _append_run_log(output_root: Path, group: str, seed: int | None, message: str) -> str:
    run_dir = _run_dir(output_root, group, seed)
    log_path = run_dir / "run.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{_utc_now()} {message}\n")
    return str(log_path)


def _write_run_status(
    output_root: Path,
    group: str,
    seed: int | None,
    *,
    status: str,
    payload: dict[str, Any],
) -> str:
    run_dir = _run_dir(output_root, group, seed)
    status_path = run_dir / "run_status.json"
    status_payload = {
        "group": group,
        "seed": seed,
        "status": status,
        "updated_at": _utc_now(),
        **payload,
    }
    status_path.write_text(json.dumps(status_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(status_path)


def _validate_paper_run_protocol(
    *,
    args: argparse.Namespace,
    output_root: Path,
    protocol: dict[str, Any] | None,
    protocol_path: Path | None,
) -> None:
    if args.run_namespace != "paper-run":
        return
    if protocol is None or protocol_path is None:
        raise FileNotFoundError(
            f"paper-run requires a frozen protocol file. Expected: {protocol_path or _default_protocol_file(args.run_namespace, args.sample)}"
        )
    if protocol.get("sample") != args.sample:
        raise ValueError(f"Protocol sample mismatch: protocol={protocol.get('sample')} args={args.sample}")
    if protocol.get("paper_run_blocked"):
        raise RuntimeError(f"paper-run protocol is blocked: {protocol['paper_run_blocked']}")

    sample_marker = f"sample_{args.sample}"
    root_text = _normal_path(output_root)
    if sample_marker not in root_text and args.sample.lower() not in root_text:
        raise RuntimeError(f"paper-run output root is not sample-isolated: {output_root}")

    data_quality = protocol.get("data_quality") or {}
    failures = [
        name
        for name in ("no_esg", "house_esg")
        if (data_quality.get(name) or {}).get("status") != "pass"
    ]
    if failures:
        raise RuntimeError(f"paper-run requires passing data quality reports; failed/missing={failures}")

    datasets = protocol.get("datasets") or {}
    allowed_paths = {
        _normal_path((datasets.get("no_esg") or {}).get("merged_dataset_path")),
        _normal_path((datasets.get("house_esg") or {}).get("merged_dataset_path")),
    }
    if _normal_path(args.dataset_path) not in allowed_paths:
        raise RuntimeError(
            "paper-run dataset path must match the frozen protocol no-ESG or house-ESG dataset. "
            f"dataset={args.dataset_path}"
        )


def _write_suite_environment(output_root: Path, snapshot: dict[str, Any]) -> str:
    protocol_dir = output_root / "protocol"
    protocol_dir.mkdir(parents=True, exist_ok=True)
    path = protocol_dir / "suite_environment_snapshot.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paper-style RL experiment suite")
    parser.add_argument("--dataset-path", default="storage/quant/demo/market.csv")
    parser.add_argument("--groups", default="B1_buyhold,B2_macd,B3_sac_noesg,B4_sac_esg,OURS_full")
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--total-steps", type=int, default=120)
    parser.add_argument("--run-namespace", default="smoke", choices=["smoke", "dev", "paper-run"])
    parser.add_argument("--sample", default="full_2022_2025", choices=["full_2022_2025", "post_esg_effective"])
    parser.add_argument("--formula-mode", default=None, choices=[None, "v2", "v2_1"], help="Formula isolation for ESG datasets.")
    parser.add_argument("--protocol-file", default=None)
    parser.add_argument("--seeds", default=None, help="Optional comma/space-separated seed override for every group.")
    parser.add_argument("--resume", action="store_true", help="Skip completed group/seed runs and continue incomplete runs.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip group/seed runs that already have metrics and equity curves.")
    parser.add_argument("--sample-output-root", default=None)
    parser.add_argument("--output-summary", default=None)
    args = parser.parse_args()

    output_root = _sample_output_root(
        namespace=args.run_namespace,
        sample=args.sample,
        formula_mode=args.formula_mode,
        sample_output_root=args.sample_output_root,
    )
    protocol, protocol_path = _load_protocol(args.protocol_file, namespace=args.run_namespace, sample=args.sample)
    _validate_paper_run_protocol(args=args, output_root=output_root, protocol=protocol, protocol_path=protocol_path)

    os.environ["QUANT_RL_EXPERIMENT_ROOT"] = str(output_root)
    get_settings.cache_clear()

    dataset_sha256 = _sha256_file(args.dataset_path)
    environment_path = _write_suite_environment(
        output_root,
        _environment_snapshot(args, dataset_sha256=dataset_sha256, protocol_file=protocol_path),
    )
    service = QuantRLService()
    seed_override = _resolve_seed_override(args.seeds)
    summary = {
        "run_namespace": args.run_namespace,
        "sample": args.sample,
        "formula_mode": args.formula_mode,
        "experiment_root": str(output_root),
        "protocol_file": str(protocol_path) if protocol_path else None,
        "environment_snapshot": environment_path,
        "dataset_path": args.dataset_path,
        "dataset_sha256": dataset_sha256,
        "groups": [],
        "ok": True,
    }

    for group_key in _resolve_groups(args.groups):
        if group_key not in EXPERIMENT_GROUPS:
            raise KeyError(f"Unknown experiment group: {group_key}")
        group_cfg = EXPERIMENT_GROUPS[group_key]
        algorithm = str(group_cfg["algorithm"])
        seeds = seed_override if seed_override is not None else (group_cfg["seeds"] or [None])
        group_result = {"group": group_key, "algorithm": algorithm, "runs": []}

        for seed in seeds:
            action_type = _action_type_for_algorithm(algorithm)
            notes = (
                f"namespace={args.run_namespace}; sample={args.sample}; protocol_group={group_key}; "
                f"seed={seed}; formula_mode={args.formula_mode}; experiment_root={output_root}"
            )
            if (args.resume or args.skip_existing) and _run_complete(output_root, group_key, seed):
                log_path = _append_run_log(output_root, group_key, seed, "skipped_existing")
                status_path = _write_run_status(
                    output_root,
                    group_key,
                    seed,
                    status="skipped_existing",
                    payload={"reason": "metrics and equity curve already exist", "log_path": log_path},
                )
                group_result["runs"].append({"seed": seed, "status": "skipped_existing", "run_status": status_path})
                continue

            log_path = _append_run_log(output_root, group_key, seed, "started")
            _write_run_status(
                output_root,
                group_key,
                seed,
                status="running",
                payload={
                    "algorithm": algorithm,
                    "dataset_path": args.dataset_path,
                    "dataset_sha256": dataset_sha256,
                    "formula_mode": args.formula_mode,
                    "sample": args.sample,
                    "log_path": log_path,
                    "gpu_at_start": _gpu_telemetry(),
                },
            )
            try:
                if algorithm in {"buy_hold", "rule_based"}:
                    backtest = service.backtest(
                        algorithm,
                        args.dataset_path,
                        action_type=action_type,
                        experiment_group=group_key,
                        seed=seed,
                        notes=notes,
                        formula_mode=args.formula_mode,
                    )
                    result = {"seed": seed, "train": None, "backtest": backtest}
                else:
                    train = service.train(
                        algorithm,
                        args.dataset_path,
                        action_type=action_type,
                        episodes=args.episodes,
                        total_steps=args.total_steps,
                        experiment_group=group_key,
                        seed=seed,
                        notes=notes,
                        formula_mode=args.formula_mode,
                    )
                    backtest = service.backtest(
                        algorithm,
                        args.dataset_path,
                        checkpoint_path=train.get("checkpoint_path"),
                        action_type=action_type,
                        experiment_group=group_key,
                        seed=seed,
                        notes=notes,
                        formula_mode=args.formula_mode,
                    )
                    result = {"seed": seed, "train": train, "backtest": backtest}
                _append_run_log(output_root, group_key, seed, "completed")
                status_path = _write_run_status(
                    output_root,
                    group_key,
                    seed,
                    status="completed",
                    payload={
                        "algorithm": algorithm,
                        "dataset_path": args.dataset_path,
                        "formula_mode": args.formula_mode,
                        "sample": args.sample,
                        "log_path": log_path,
                        "gpu_at_end": _gpu_telemetry(),
                        "metrics": result.get("backtest", {}).get("metrics", {}),
                    },
                )
                result["status"] = "completed"
                result["run_status"] = status_path
                group_result["runs"].append(result)
            except Exception as exc:
                summary["ok"] = False
                _append_run_log(output_root, group_key, seed, f"failed: {exc}")
                status_path = _write_run_status(
                    output_root,
                    group_key,
                    seed,
                    status="failed",
                    payload={
                        "algorithm": algorithm,
                        "dataset_path": args.dataset_path,
                        "formula_mode": args.formula_mode,
                        "sample": args.sample,
                        "log_path": log_path,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "gpu_at_failure": _gpu_telemetry(),
                    },
                )
                group_result["runs"].append({"seed": seed, "status": "failed", "run_status": status_path, "error": str(exc)})
                summary["groups"].append(group_result)
                raise

        summary["groups"].append(group_result)

    output_path = Path(args.output_summary) if args.output_summary else output_root / "summary" / f"experiment_suite_{args.sample}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    summary["output_path"] = str(output_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
