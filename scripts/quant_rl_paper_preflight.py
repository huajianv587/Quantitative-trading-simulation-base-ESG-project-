#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_EMBEDDING_MODEL = "text-embedding-3-large"
EXPECTED_EMBEDDING_DIMENSION = 3072
EXPECTED_MISSING_2025 = 10
EXPECTED_YEARS = {2022, 2023, 2024, 2025}


def _check(condition: bool, name: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if condition else "fail",
        "message": message,
        "details": details or {},
    }


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _cuda_available() -> tuple[bool, str]:
    assumed = os.getenv("QUANT_RL_PREFLIGHT_ASSUME_CUDA")
    if assumed is not None:
        return assumed.strip() == "1", "env_override"
    try:
        import torch
    except Exception as exc:
        return False, f"torch_unavailable: {exc}"
    try:
        return bool(torch.cuda.is_available()), f"torch={torch.__version__} cuda={getattr(torch.version, 'cuda', None)}"
    except Exception as exc:
        return False, str(exc)


def run_preflight(*, namespace: str, sample: str, require_cuda: bool, allow_cpu_smoke: bool, output_path: Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    json_paths = [
        ROOT / "storage" / "esg_corpus" / "manifest.json",
        ROOT / "storage" / "esg_corpus" / "coverage_report.json",
        ROOT / "storage" / "esg_corpus" / "evidence_chain_report.json",
        ROOT / "storage" / "esg_corpus" / "house_scores_v2.json",
        ROOT / "storage" / "rag" / "esg_reports_openai_3072" / "embedding_manifest.json",
    ]
    summary_path = ROOT / "storage" / "quant" / "rl-experiments" / namespace / "summary" / f"esg_rl_2022_2025_pipeline_{sample}.json"
    if summary_path.exists():
        json_paths.append(summary_path)

    loaded: dict[str, Any] = {}
    for path in json_paths:
        payload, error = _load_json(path)
        checks.append(_check(payload is not None and error is None, "json_parseable", f"JSON is parseable: {path}", details={"path": str(path), "error": error}))
        if payload is not None:
            loaded[str(path)] = payload

    embedding_manifest = loaded.get(str(ROOT / "storage" / "rag" / "esg_reports_openai_3072" / "embedding_manifest.json")) or {}
    embedding_chunks = int(embedding_manifest.get("chunks") or 0)
    current_chunks = int(embedding_manifest.get("current_corpus_chunks") or embedding_chunks or 0)
    checks.append(_check(
        embedding_manifest.get("model") == EXPECTED_EMBEDDING_MODEL,
        "embedding_model",
        "Embedding manifest uses the formal paper model.",
        details={"expected": EXPECTED_EMBEDDING_MODEL, "actual": embedding_manifest.get("model")},
    ))
    checks.append(_check(
        int(embedding_manifest.get("dimension") or 0) == EXPECTED_EMBEDDING_DIMENSION,
        "embedding_dimension",
        "Embedding dimension matches text-embedding-3-large.",
        details={"expected": EXPECTED_EMBEDDING_DIMENSION, "actual": embedding_manifest.get("dimension")},
    ))
    checks.append(_check(
        embedding_chunks > 0 and current_chunks == embedding_chunks,
        "embedding_chunk_count",
        "Embedding chunk counts are non-empty and internally consistent.",
        details={"chunks": embedding_chunks, "current_corpus_chunks": current_chunks},
    ))

    manifest = loaded.get(str(ROOT / "storage" / "esg_corpus" / "manifest.json")) or {}
    records = list(manifest.get("records") or embedding_manifest.get("records") or [])
    manifest_years = {int(record.get("year")) for record in records if str(record.get("year", "")).isdigit()}
    bad_year_records = [
        record
        for record in records
        if int(record.get("year") or 0) not in EXPECTED_YEARS
        or "2026" in str(record.get("local_path") or "")
    ]
    checks.append(_check(
        not bad_year_records and manifest_years.issubset(EXPECTED_YEARS),
        "manifest_year_bounds",
        "2026 files are excluded from the 2022-2025 formal manifest.",
        details={"manifest_years": sorted(manifest_years), "bad_records": len(bad_year_records)},
    ))
    missing_2025 = [
        record
        for record in records
        if int(record.get("year") or 0) == 2025
        and record.get("download_status") in {"not_published_yet", "not_published_or_not_found"}
        and not record.get("local_path")
    ]
    checks.append(_check(
        len(missing_2025) == EXPECTED_MISSING_2025,
        "missing_2025_accounting",
        "The expected missing 2025 reports are explicitly recorded.",
        details={"expected": EXPECTED_MISSING_2025, "actual": len(missing_2025), "tickers": sorted({str(record.get("ticker")) for record in missing_2025})},
    ))

    cuda_ok, cuda_detail = _cuda_available()
    checks.append(_check(
        cuda_ok or not require_cuda or allow_cpu_smoke,
        "cuda_required",
        "CUDA is visible for paper-run, or CPU smoke was explicitly allowed.",
        details={"cuda_available": cuda_ok, "detail": cuda_detail, "require_cuda": require_cuda, "allow_cpu_smoke": allow_cpu_smoke},
    ))

    failed = [check for check in checks if check["status"] == "fail"]
    payload = {
        "status": "fail" if failed else "pass",
        "namespace": namespace,
        "sample": sample,
        "checks": checks,
        "fail_count": len(failed),
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        payload["output_path"] = str(output_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Final paper-run preflight before 5090 ESG/RL training.")
    parser.add_argument("--namespace", "--run-namespace", default="paper-run")
    parser.add_argument("--sample", default="full_2022_2025", choices=["full_2022_2025", "post_esg_effective"])
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--allow-cpu-smoke", action="store_true")
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()
    output_path = Path(args.output_path) if args.output_path else None
    report = run_preflight(
        namespace=args.namespace,
        sample=args.sample,
        require_cuda=args.require_cuda,
        allow_cpu_smoke=args.allow_cpu_smoke,
        output_path=output_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
