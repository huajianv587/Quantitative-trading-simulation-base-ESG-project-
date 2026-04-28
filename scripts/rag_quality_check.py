#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_FILE = PROJECT_ROOT / "configs" / "rag_quality_samples.json"
DEFAULT_BASE_URL = "http://localhost:8012"
FAILURE_MARKERS = (
    "retrieval failed",
    "analysis failed",
    "no context available",
    "analysis unavailable",
    "all llm backends failed",
)


def load_samples(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Sample file must contain a non-empty JSON array.")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Sample #{index} must be an object.")
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"Sample #{index} is missing question.")
        normalized.append(
            {
                "name": str(item.get("name") or f"sample_{index}"),
                "question": question,
                "require_scores": bool(item.get("require_scores", False)),
                "min_answer_chars": int(item.get("min_answer_chars", 120)),
                "min_confidence": float(item.get("min_confidence", 0.35)),
            }
        )
    return normalized


def http_json(url: str, timeout: int = 180) -> tuple[int, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "rag-quality-check/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.getcode(), json.loads(response.read().decode("utf-8", errors="ignore"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc


def wait_for_rag_ready(base_url: str, retries: int, delay: float, timeout: int) -> bool:
    for attempt in range(1, retries + 1):
        try:
            status, payload = http_json(f"{base_url}/health", timeout=timeout)
            if status == 200 and bool(payload.get("modules", {}).get("rag")):
                print(f"[OK] RAG module ready after {attempt} check(s).")
                return True
            print(f"[WAIT] /health ready={payload.get('modules', {}).get('rag')} (attempt {attempt}/{retries})")
        except Exception as exc:
            print(f"[WAIT] health check failed on attempt {attempt}/{retries}: {exc}")
        time.sleep(delay)
    return False


def run_http_sample(base_url: str, sample: dict[str, Any], timeout: int) -> dict[str, Any]:
    params = urlencode(
        {
            "question": sample["question"],
            "session_id": f"qa_{sample['name']}_{int(time.time())}",
        }
    )
    url = f"{base_url}/agent/analyze?{params}"
    started = time.perf_counter()
    status, payload = http_json(url, timeout=timeout)
    latency = time.perf_counter() - started
    return {
        "sample": sample,
        "status_code": status,
        "payload": payload,
        "latency_seconds": round(latency, 2),
    }


def run_graph_sample(sample: dict[str, Any], rebuild: bool) -> dict[str, Any]:
    from gateway.agents.graph import run_agent
    from gateway.rag.rag_main import get_query_engine

    if rebuild:
        get_query_engine(force_rebuild=True)
        rebuild = False

    started = time.perf_counter()
    payload = run_agent(sample["question"], session_id=f"qa_{sample['name']}")
    latency = time.perf_counter() - started
    return {
        "sample": sample,
        "status_code": 200,
        "payload": {
            "question": sample["question"],
            "answer": payload.get("final_answer", ""),
            "esg_scores": payload.get("esg_scores", {}),
            "confidence": payload.get("confidence", 0.0),
            "analysis_summary": payload.get("analysis_summary", ""),
            "task_type": payload.get("task_type", ""),
            "is_grounded": payload.get("is_grounded", False),
        },
        "latency_seconds": round(latency, 2),
    }


def evaluate_result(result: dict[str, Any]) -> dict[str, Any]:
    sample = result["sample"]
    payload = result.get("payload") or {}
    answer = str(payload.get("answer", "")).strip()
    confidence = float(payload.get("confidence") or 0.0)
    esg_scores = payload.get("esg_scores") or {}

    checks: list[str] = []
    passed = True

    if result.get("status_code") != 200:
        checks.append(f"status={result.get('status_code')}")
        passed = False

    if len(answer) < sample["min_answer_chars"]:
        checks.append(f"answer_too_short:{len(answer)}<{sample['min_answer_chars']}")
        passed = False

    if confidence < sample["min_confidence"]:
        checks.append(f"confidence_too_low:{confidence:.2f}<{sample['min_confidence']:.2f}")
        passed = False

    if sample["require_scores"] and not esg_scores:
        checks.append("missing_esg_scores")
        passed = False

    lowered = answer.lower()
    if any(marker in lowered for marker in FAILURE_MARKERS):
        checks.append("failure_marker_in_answer")
        passed = False

    if sample["require_scores"] and not str(payload.get("analysis_summary", "")).strip():
        checks.append("missing_analysis_summary")
        passed = False

    return {
        **result,
        "passed": passed,
        "checks": checks,
        "answer_chars": len(answer),
        "confidence": round(confidence, 4),
        "has_esg_scores": bool(esg_scores),
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed_count = sum(1 for item in results if item["passed"])
    failed = [item for item in results if not item["passed"]]
    avg_confidence = round(
        sum(item.get("confidence", 0.0) for item in results) / max(len(results), 1),
        4,
    )
    avg_latency = round(
        sum(float(item.get("latency_seconds", 0.0)) for item in results) / max(len(results), 1),
        2,
    )
    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(failed),
        "pass_rate": round(passed_count / max(len(results), 1), 4),
        "average_confidence": avg_confidence,
        "average_latency_seconds": avg_latency,
        "failed_samples": [
            {
                "name": item["sample"]["name"],
                "checks": item["checks"],
                "status_code": item["status_code"],
            }
            for item in failed
        ],
    }


def print_summary(summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    print("== RAG Quality Check ==")
    for item in results:
        sample = item["sample"]
        status = "PASS" if item["passed"] else "FAIL"
        print(
            f"[{status}] {sample['name']} | latency={item['latency_seconds']}s | "
            f"confidence={item['confidence']:.2f} | answer_chars={item['answer_chars']}"
        )
        if item["checks"]:
            print(f"       checks: {', '.join(item['checks'])}")

    print(
        f"[SUMMARY] pass_rate={summary['pass_rate']:.2%} "
        f"({summary['passed']}/{summary['total']}), "
        f"avg_confidence={summary['average_confidence']:.2f}, "
        f"avg_latency={summary['average_latency_seconds']:.2f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sampled RAG quality checks.")
    parser.add_argument("--mode", choices=["http", "graph"], default="http")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--sample-file", type=Path, default=DEFAULT_SAMPLE_FILE)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--wait-rag-ready", action="store_true")
    parser.add_argument("--retries", type=int, default=20)
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    if args.mode == "http" and args.rebuild:
        print("[FAIL] --rebuild is only supported in graph mode.", file=sys.stderr)
        return 2

    samples = load_samples(args.sample_file)
    results: list[dict[str, Any]] = []

    if args.mode == "http" and args.wait_rag_ready:
        if not wait_for_rag_ready(args.base_url, args.retries, args.delay, args.timeout):
            print("[FAIL] RAG module did not become ready in time.")
            return 1

    rebuild = args.rebuild
    for sample in samples:
        if args.mode == "http":
            raw_result = run_http_sample(args.base_url, sample, args.timeout)
        else:
            raw_result = run_graph_sample(sample, rebuild=rebuild)
            rebuild = False
        results.append(evaluate_result(raw_result))

    summary = summarize_results(results)
    print_summary(summary, results)

    if args.output_json:
        args.output_json.write_text(
            json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
