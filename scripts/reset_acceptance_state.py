from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_DIR = PROJECT_ROOT / "storage" / "quant"
COLLECTIONS = [
    "jobs",
    "job_events",
    "reports",
    "paper_outcomes",
    "paper_performance",
    "paper_cash_flows",
    "paper_daily_digests",
    "paper_weekly_digests",
    "workflow_runs",
    "scheduler_events",
    "session_evidence",
    "submit_locks",
    "push_rules",
    "subscriptions",
    "strategy_registry",
    "strategy_allocations",
    "autopilot_policies",
    "daily_reviews",
    "debate_runs",
    "data_source_configs",
    "provider_health_checks",
    "data_quality_runs",
]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_under(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    root = parent.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to operate outside {root}: {resolved}") from exc
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _matches_namespace(path: Path, payload: dict[str, Any], namespace: str) -> bool:
    stem = path.stem.lower()
    ns = namespace.lower()
    if stem.startswith(f"{ns}-") or stem.startswith(f"acceptance-{ns}-") or stem.startswith("acceptance-"):
        return True
    for key in ("acceptance_namespace", "namespace", "test_namespace"):
        if str(payload.get(key) or "").lower() == ns:
            return True
    nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    for key in ("acceptance_namespace", "namespace", "test_namespace"):
        if str(nested.get(key) or "").lower() == ns:
            return True
    return False


def reset_acceptance_state(namespace: str, base_dir: Path, dry_run: bool) -> dict[str, Any]:
    safe_base = _resolve_under(base_dir, PROJECT_ROOT)
    acceptance_root = _resolve_under(safe_base / "acceptance", safe_base)
    namespace_root = _resolve_under(acceptance_root / namespace, acceptance_root)
    removed: list[str] = []
    skipped: list[str] = []

    if namespace_root.exists():
        removed.append(str(namespace_root))
        if not dry_run:
            shutil.rmtree(namespace_root)

    for collection in COLLECTIONS:
        directory = safe_base / collection
        if not directory.exists():
            continue
        safe_dir = _resolve_under(directory, safe_base)
        for path in safe_dir.glob("*.json"):
            safe_path = _resolve_under(path, safe_dir)
            payload = _load_json(safe_path)
            if _matches_namespace(safe_path, payload, namespace):
                removed.append(str(safe_path))
                if not dry_run:
                    safe_path.unlink(missing_ok=True)
            else:
                skipped.append(str(safe_path))

    report = {
        "generated_at": _iso_now(),
        "namespace": namespace,
        "base_dir": str(safe_base),
        "dry_run": dry_run,
        "removed": removed,
        "skipped_count": len(skipped),
        "status": "ready",
    }
    if not dry_run:
        namespace_root.mkdir(parents=True, exist_ok=True)
        (namespace_root / "reset-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset local acceptance state safely by namespace.")
    parser.add_argument("--namespace", default=None, help="Acceptance namespace. Defaults to ACCEPTANCE_NAMESPACE or default.")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Quant storage base directory.")
    parser.add_argument("--dry-run", action="store_true", help="List matching records without deleting them.")
    args = parser.parse_args()

    namespace = (args.namespace or __import__("os").environ.get("ACCEPTANCE_NAMESPACE") or "default").strip()
    if not namespace or namespace in {".", ".."}:
        raise SystemExit("Invalid namespace.")
    report = reset_acceptance_state(namespace=namespace, base_dir=Path(args.base_dir), dry_run=bool(args.dry_run))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

