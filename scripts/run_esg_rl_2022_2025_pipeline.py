#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.reporting.experiment_recorder import MANUAL_STOCK_UNIVERSE
from quant_rl.infrastructure.settings import get_settings
from quant_rl.service.quant_service import QuantRLService
from scripts.esg_corpus_pipeline import (
    EXPERIMENT_PERIOD,
    EMBED_ROOT,
    YEARS,
    build_manifest,
    coverage_summary,
    embed_records,
    rag_quality,
    score_records,
    set_corpus_root,
    _write_manifest,
)
from scripts.quant_rl_data_quality_gate import run_quality_gate


def _all_symbols() -> list[str]:
    symbols: list[str] = []
    for values in MANUAL_STOCK_UNIVERSE.values():
        symbols.extend(values)
    return symbols


def _namespace_root(namespace: str) -> Path:
    return ROOT / "storage" / "quant" / "rl-experiments" / namespace


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def _score_rows(score_summary: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(score_summary.get("json_path") or "")
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _post_esg_start(score_summary: dict[str, Any], fallback: str) -> str:
    dates = sorted(
        str(row.get("effective_date"))
        for row in _score_rows(score_summary)
        if row.get("score_available") and row.get("effective_date")
    )
    return dates[0] if dates else fallback


def _coverage_gate(coverage: dict[str, Any], *, namespace: str) -> dict[str, Any]:
    """Strict paper-run coverage check before expensive data or training jobs."""
    by_ticker = coverage.get("by_ticker") or {}
    required_years = {str(year) for year in YEARS}
    blocking_years = {str(year) for year in YEARS if year < 2025}
    universe_symbols: set[str] = set()
    for values in MANUAL_STOCK_UNIVERSE.values():
        universe_symbols.update(str(symbol).upper() for symbol in values)
    missing_tickers = sorted(universe_symbols - set(by_ticker))
    weak: list[dict[str, Any]] = []
    for ticker, item in sorted(by_ticker.items()):
        present_years = {str(year) for year in (item.get("present_years") or [])}
        missing_required = sorted(year for year in required_years if year not in present_years)
        missing_blocking = sorted(year for year in blocking_years if year not in present_years)
        if missing_required or missing_blocking:
            weak.append({
                "ticker": ticker,
                "missing_years": missing_required,
                "blocking_missing_years": missing_blocking,
            })
    hard_fail = bool(missing_tickers or any(item["blocking_missing_years"] for item in weak))
    status = "fail" if namespace == "paper-run" and hard_fail else "pass"
    return {
        "status": status,
        "companies_total": coverage.get("companies_total"),
        "companies_with_any_report": coverage.get("companies_with_any_report"),
        "missing_tickers": missing_tickers,
        "weak_coverage": weak,
        "rule": "paper-run requires all 20 tickers and non-missing 2022-2024 local ESG evidence; 2025 may be missing if explicitly recorded.",
    }


def _embedding_status(model: str) -> dict[str, Any]:
    embedding_path = EMBED_ROOT / "embeddings.jsonl"
    manifest_path = EMBED_ROOT / "embedding_manifest.json"
    if not embedding_path.exists():
        return {
            "status": "missing",
            "model": model,
            "output_path": str(embedding_path),
            "reason": "Run with --embed to call OpenAI embeddings.",
        }
    chunks = 0
    with embedding_path.open("r", encoding="utf-8") as handle:
        chunks = sum(1 for line in handle if line.strip())
    payload: dict[str, Any] = {
        "status": "existing",
        "model": model,
        "output_path": str(embedding_path),
        "chunks": chunks,
    }
    if manifest_path.exists():
        try:
            payload["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            payload["manifest_path"] = str(manifest_path)
    return payload


def _write_frozen_inputs(namespace: str, sample: str, payload: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    out_dir = _namespace_root(namespace) / "protocol"
    out_dir.mkdir(parents=True, exist_ok=True)
    frozen = {
        "namespace": namespace,
        "sample": sample,
        "git_commit": _git_commit(),
        "arguments": vars(args),
        "experiment_period": payload.get("experiment_period"),
        "manifest": payload.get("manifest"),
        "coverage": payload.get("coverage"),
        "coverage_gate": payload.get("coverage_gate"),
        "score": payload.get("score"),
        "rag": payload.get("rag"),
        "embedding": payload.get("embedding"),
        "datasets": payload.get("datasets"),
        "data_quality": payload.get("data_quality"),
        "formal_training_protocol": payload.get("formal_training_protocol"),
        "paper_run_blocked": payload.get("paper_run_blocked"),
    }
    path = out_dir / f"frozen_inputs_{sample}.json"
    path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    latest_path = out_dir / "frozen_inputs_latest.json"
    latest_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"frozen_inputs_path": str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 2022-2025 ESG/RL data preparation pipeline.")
    parser.add_argument("--embed", action="store_true", help="Call OpenAI embeddings. Off by default to avoid accidental spend.")
    parser.add_argument("--build-datasets", action="store_true", help="Build L4 no-ESG and L5 ESG RL datasets from Alpaca-first data.")
    parser.add_argument("--symbols", default=",".join(_all_symbols()))
    parser.add_argument("--limit", type=int, default=1300)
    parser.add_argument("--start-date", default=EXPERIMENT_PERIOD["train"][0])
    parser.add_argument("--end-date", default=EXPERIMENT_PERIOD["test"][1])
    parser.add_argument("--run-namespace", default="smoke", choices=["smoke", "dev", "paper-run"])
    parser.add_argument("--sample", default="full_2022_2025", choices=["full_2022_2025", "post_esg_effective"])
    parser.add_argument("--embedding-model", default="text-embedding-3-large")
    parser.add_argument("--corpus-root", default="esg_reports")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--max-chunks-per-doc", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=24)
    args = parser.parse_args()

    set_corpus_root(args.corpus_root)
    records = build_manifest(download=False, force=False, limit=None, timeout=30)
    manifest = _write_manifest(records)
    embedding: dict[str, Any]
    if args.embed:
        try:
            embedding = embed_records(
                records,
                model=args.embedding_model,
                max_pages=args.max_pages,
                max_chunks_per_doc=args.max_chunks_per_doc,
                batch_size=args.batch_size,
            )
            manifest = _write_manifest(records)
        except Exception as exc:
            if args.run_namespace == "paper-run":
                raise
            embedding = {
                "status": "failed",
                "model": args.embedding_model,
                "reason": str(exc),
            }
    else:
        embedding = _embedding_status(args.embedding_model)
    rag = rag_quality(records, evidence_chain=True)
    score = score_records(records)
    sample_start = _post_esg_start(score, args.start_date) if args.sample == "post_esg_effective" else args.start_date
    sample_end = args.end_date
    namespace_root = _namespace_root(args.run_namespace)
    os.environ["QUANT_RL_EXPERIMENT_ROOT"] = str(namespace_root)
    get_settings.cache_clear()

    coverage = coverage_summary(records)
    coverage_gate = _coverage_gate(coverage, namespace=args.run_namespace)
    payload: dict[str, Any] = {
        "experiment_period": EXPERIMENT_PERIOD,
        "run_namespace": args.run_namespace,
        "sample": args.sample,
        "formula_modes": ["v2", "v2_1"],
        "formal_training_protocol": {
            "samples": ["full_2022_2025", "post_esg_effective"],
            "formula_modes": ["v2", "v2_1"],
            "groups": [
                "B1_buyhold",
                "B2_macd",
                "B3_sac_noesg",
                "B4_sac_esg",
                "OURS_full",
                "6a_no_esg_obs",
                "6b_no_esg_reward",
                "6c_no_regime",
            ],
            "seeds": [42, 123, 456],
            "formal_total_steps": 500000,
            "formal_episodes": 50,
            "smoke_total_steps": 120,
            "smoke_episodes": 3,
        },
        "sample_period": {"start_date": sample_start, "end_date": sample_end},
        "coverage": coverage,
        "coverage_gate": coverage_gate,
        "manifest": manifest,
        "score": score,
        "rag": rag,
        "embedding": embedding,
        "datasets": {},
        "data_quality": {},
    }

    block_reasons: list[dict[str, Any]] = []
    if args.run_namespace == "paper-run":
        if coverage_gate.get("status") == "fail":
            block_reasons.append({"reason": "coverage_gate_failed", "details": coverage_gate})
        if payload["embedding"].get("status") == "missing":
            block_reasons.append({"reason": "embedding_missing", "details": payload["embedding"]})
        elif int(payload["embedding"].get("chunks") or payload["embedding"].get("current_corpus_chunks") or 0) <= 0:
            block_reasons.append({"reason": "embedding_empty", "details": payload["embedding"]})
    if block_reasons:
        payload["paper_run_blocked"] = {"reason": "pre_dataset_gate_failed", "failures": block_reasons}

    should_build_datasets = args.build_datasets and not (args.run_namespace == "paper-run" and payload.get("paper_run_blocked"))
    if should_build_datasets:
        service = QuantRLService()
        symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
        min_rows = 20
        if args.run_namespace == "paper-run":
            min_rows = 700 if args.sample == "full_2022_2025" else 500
        common = {
            "limit": args.limit,
            "force_refresh": False,
            "symbols": symbols,
            "start_date": sample_start,
            "end_date": sample_end,
        }
        payload["datasets"]["no_esg"] = service.build_recipe_dataset(
            "L4_fundamental",
            dataset_name=f"{args.run_namespace}_{args.sample}_l4_no_esg",
            **common,
        )
        payload["datasets"]["house_esg"] = service.build_recipe_dataset(
            "L5_house_esg",
            dataset_name=f"{args.run_namespace}_{args.sample}_l5_house_esg",
            **common,
        )
        quality_dir = namespace_root / "quality" / args.sample
        payload["data_quality"]["no_esg"] = run_quality_gate(
            dataset_path=payload["datasets"]["no_esg"]["merged_dataset_path"],
            namespace=args.run_namespace,
            dataset_kind="no-esg",
            expected_symbols=symbols,
            start_date=sample_start,
            end_date=sample_end,
            output_dir=quality_dir / "no_esg",
            min_rows_per_symbol=min_rows,
        )
        payload["data_quality"]["house_esg"] = run_quality_gate(
            dataset_path=payload["datasets"]["house_esg"]["merged_dataset_path"],
            paired_dataset_path=payload["datasets"]["no_esg"]["merged_dataset_path"],
            namespace=args.run_namespace,
            dataset_kind="house-esg",
            expected_symbols=symbols,
            start_date=sample_start,
            end_date=sample_end,
            output_dir=quality_dir / "house_esg",
            min_rows_per_symbol=min_rows,
        )
        if args.run_namespace == "paper-run":
            failed = [
                name
                for name, report in payload["data_quality"].items()
                if report.get("status") == "fail"
            ]
            if failed:
                payload["paper_run_blocked"] = {"reason": "data_quality_gate_failed", "failed_reports": failed}
    elif args.build_datasets:
        payload["datasets"]["status"] = "skipped"
        payload["datasets"]["reason"] = "paper-run pre-dataset gate failed; fix coverage/embedding before building formal datasets."

    payload["protocol"] = _write_frozen_inputs(args.run_namespace, args.sample, payload, args)
    output_dir = namespace_root / "summary"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"esg_rl_2022_2025_pipeline_{args.sample}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "coverage": payload["coverage"], "score": score}, ensure_ascii=False, indent=2, default=str))
    if args.run_namespace == "paper-run" and payload.get("paper_run_blocked"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
