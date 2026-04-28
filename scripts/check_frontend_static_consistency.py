from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "frontend" / "js"
DIST_ROOT = PROJECT_ROOT / "dist" / "app" / "js"
KEY_FILES = (
    "qtapi.js",
    "utils.js",
    "pages/dashboard.js",
    "pages/execution.js",
    "pages/portfolio.js",
    "pages/portfolio-lab.js",
    "pages/research.js",
    "pages/rl-lab.js",
    "pages/trading-ops.js",
    "pages/workbench-utils.js",
    "utils/cache-manager.js",
    "utils/lazy-load.js",
)
AUTH_CONTRACT_TOKENS = (
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/reset-password/request",
    "function _scopeForRequest",
    "__ESG_RESEARCH_API_KEY__",
    "__ESG_TRADING_API_KEY__",
)
STORAGE_CONTRACT_TOKENS = {
    "utils.js": (
        "exportfunctionsetVersionedStorageValue",
        "exportfunctiongetVersionedStorageValue",
        "storage.removeItem(key)",
    ),
    "pages/dashboard.js": (
        "EXECUTION_PREFILL_STORAGE_KEY",
        "setVersionedStorageValue(window.sessionStorage,EXECUTION_PREFILL_STORAGE_KEY",
    ),
    "pages/execution.js": (
        "WORKFLOW_LATEST_STORAGE_KEY",
        "getVersionedStorageValue(window.localStorage,WORKFLOW_LATEST_STORAGE_KEY",
        "setVersionedStorageValue(window.localStorage,WORKFLOW_LATEST_STORAGE_KEY",
    ),
    "pages/portfolio.js": (
        "PORTFOLIO_PREFILL_STORAGE_KEY",
        "EXECUTION_PREFILL_STORAGE_KEY",
        "getVersionedStorageValue(window.sessionStorage,PORTFOLIO_PREFILL_STORAGE_KEY",
        "setVersionedStorageValue(window.sessionStorage,EXECUTION_PREFILL_STORAGE_KEY",
    ),
    "pages/portfolio-lab.js": (
        "EXECUTION_PREFILL_STORAGE_KEY",
        "setVersionedStorageValue(window.sessionStorage,EXECUTION_PREFILL_STORAGE_KEY",
    ),
    "pages/research.js": (
        "PORTFOLIO_PREFILL_STORAGE_KEY",
        "setVersionedStorageValue(window.sessionStorage,PORTFOLIO_PREFILL_STORAGE_KEY",
    ),
    "pages/rl-lab.js": (
        "WORKFLOW_LATEST_STORAGE_KEY",
        "setVersionedStorageValue(window.localStorage,WORKFLOW_LATEST_STORAGE_KEY",
    ),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_js(root: Path):
    if not root.exists():
        return
    yield from root.rglob("*.js")


def _scan_process_env(root: Path) -> list[str]:
    failures: list[str] = []
    for path in _iter_js(root):
        text = _read(path)
        if "process.env" not in text:
            continue
        if "typeof process !== 'undefined'" not in text and 'typeof process !== "undefined"' not in text:
            failures.append(str(path.relative_to(PROJECT_ROOT)))
    return failures


def _check_auth_contract(path: Path) -> list[str]:
    text = _read(path)
    failures = [token for token in AUTH_CONTRACT_TOKENS if token not in text]
    legacy_call = re.search(r"_post\(\s*['\"]/(auth/(login|register|reset-password))", text)
    if legacy_call:
        failures.append(f"legacy auth call path: {legacy_call.group(0)}")
    return failures


def _check_storage_contract(path: Path, relative: str) -> list[str]:
    text = _read(path)
    compact = "".join(text.split())
    return [token for token in STORAGE_CONTRACT_TOKENS.get(relative, ()) if token not in compact]


def main() -> int:
    failures: list[str] = []
    report: dict[str, object] = {
        "source_root": str(SOURCE_ROOT),
        "dist_root": str(DIST_ROOT),
        "key_files": [],
        "process_env_guard": {},
        "auth_contract": {},
        "storage_contract": {},
    }

    if not SOURCE_ROOT.exists():
        failures.append(f"missing source frontend js root: {SOURCE_ROOT}")
    if not DIST_ROOT.exists():
        failures.append(f"missing dist frontend js root: {DIST_ROOT}; run npm run build:static")

    for relative in KEY_FILES:
        source = SOURCE_ROOT / relative
        dist = DIST_ROOT / relative
        item = {"path": relative, "source_exists": source.exists(), "dist_exists": dist.exists()}
        if not source.exists() or not dist.exists():
            failures.append(f"missing key frontend file pair: {relative}")
        else:
            source_hash = _sha256(source)
            dist_hash = _sha256(dist)
            item["source_sha256"] = source_hash
            item["dist_sha256"] = dist_hash
            if source_hash != dist_hash:
                failures.append(f"dist/app is stale for {relative}; run npm run build:static")
        report["key_files"].append(item)

    for label, root in (("frontend", SOURCE_ROOT), ("dist", DIST_ROOT)):
        process_env_failures = _scan_process_env(root)
        report["process_env_guard"][label] = process_env_failures
        failures.extend(f"unguarded process.env in {path}" for path in process_env_failures)

    for label, root in (("frontend", SOURCE_ROOT), ("dist", DIST_ROOT)):
        qtapi_path = root / "qtapi.js"
        if not qtapi_path.exists():
            continue
        auth_failures = _check_auth_contract(qtapi_path)
        report["auth_contract"][label] = auth_failures
        failures.extend(f"{label}/qtapi.js auth contract drift: {item}" for item in auth_failures)

    for label, root in (("frontend", SOURCE_ROOT), ("dist", DIST_ROOT)):
        label_report: dict[str, list[str]] = {}
        for relative in STORAGE_CONTRACT_TOKENS:
            path = root / relative
            if not path.exists():
                contract_failures = [f"missing storage contract file: {relative}"]
            else:
                contract_failures = _check_storage_contract(path, relative)
            label_report[relative] = contract_failures
            failures.extend(f"{label}/{relative} storage contract drift: {item}" for item in contract_failures)
        report["storage_contract"][label] = label_report

    report["ok"] = not failures
    report["failures"] = failures
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
