from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from blueprint_runtime import (
    build_reporting_production,
    check_infrastructure_production,
    evaluate_risk_suite_production,
    predict_model_production,
    run_advanced_backtest_production,
    run_analysis_production,
    run_data_pipeline_production,
    train_model_production,
)
from gateway.config import settings
from gateway.db.supabase_client import latest_table_row, list_table_rows, save_table_row, update_table_row
from gateway.quant.storage import QuantStorageGateway

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = PROJECT_ROOT / "database" / "migrations" / "006_create_production_ops.sql"
JOB_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled", "degraded", "blocked"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "degraded", "blocked"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _production_mode() -> bool:
    return str(os.getenv("APP_MODE") or "").strip().lower() == "production"


def _remote_enabled(name: str) -> bool:
    return _env_bool(name, _production_mode())


def _mask_secret(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


REQUIRED_TABLES: list[dict[str, Any]] = [
    {
        "table": "strategy_registry",
        "domain": "trading/autopilot",
        "business_key": "strategy_id",
        "required_columns": ["id", "strategy_id", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "strategy_allocations",
        "domain": "trading/autopilot",
        "business_key": "allocation_id",
        "required_columns": ["id", "allocation_id", "strategy_id", "payload", "created_at", "updated_at"],
    },
    {
        "table": "autopilot_policies",
        "domain": "trading/autopilot",
        "business_key": "policy_id",
        "required_columns": ["id", "policy_id", "effective_mode", "payload", "created_at", "updated_at"],
    },
    {
        "table": "debate_runs",
        "domain": "trading/autopilot",
        "business_key": "debate_id",
        "required_columns": ["id", "debate_id", "symbol", "payload", "created_at", "updated_at"],
    },
    {
        "table": "daily_reviews",
        "domain": "trading/autopilot",
        "business_key": "review_id",
        "required_columns": ["id", "review_id", "session_date", "payload", "created_at", "updated_at"],
    },
    {
        "table": "paper_performance_snapshots",
        "domain": "paper evidence",
        "business_key": "snapshot_id",
        "required_columns": ["id", "snapshot_id", "session_date", "payload", "created_at", "updated_at"],
    },
    {
        "table": "paper_outcomes",
        "domain": "paper evidence",
        "business_key": "outcome_id",
        "required_columns": ["id", "outcome_id", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "session_evidence",
        "domain": "paper evidence",
        "business_key": "session_date",
        "required_columns": ["id", "session_date", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "scheduler_events",
        "domain": "paper evidence",
        "business_key": "event_id",
        "required_columns": ["id", "event_id", "stage", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "submit_locks",
        "domain": "paper evidence",
        "business_key": "lock_key",
        "required_columns": ["id", "lock_key", "session_date", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "quant_jobs",
        "domain": "job queue",
        "business_key": "job_id",
        "required_columns": ["id", "job_id", "job_type", "status", "payload", "result", "created_at", "updated_at"],
    },
    {
        "table": "quant_job_events",
        "domain": "job queue",
        "business_key": "event_id",
        "required_columns": ["id", "event_id", "job_id", "event_type", "status", "payload", "created_at"],
    },
    {
        "table": "data_source_configs",
        "domain": "data config",
        "business_key": "provider_id",
        "required_columns": ["id", "provider_id", "priority", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "provider_health_checks",
        "domain": "data config",
        "business_key": "check_id",
        "required_columns": ["id", "check_id", "provider_id", "status", "payload", "created_at", "updated_at"],
    },
    {
        "table": "data_quality_runs",
        "domain": "data config",
        "business_key": "run_id",
        "required_columns": ["id", "run_id", "dataset_id", "status", "payload", "created_at", "updated_at"],
    },
]


PROVIDER_SPECS: list[dict[str, Any]] = [
    {"provider_id": "yfinance", "label": "Yahoo Finance", "domain": "prices", "required_env": [], "mode": "real_or_cache"},
    {"provider_id": "alpaca_paper", "label": "Alpaca Paper", "domain": "prices/execution", "required_env": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"], "mode": "real"},
    {"provider_id": "fred", "label": "FRED", "domain": "macro", "required_env": ["FRED_API_KEY"], "mode": "real"},
    {"provider_id": "sec", "label": "SEC EDGAR", "domain": "fundamentals/sec", "required_env": ["SEC_USER_AGENT"], "mode": "real"},
    {"provider_id": "newsapi", "label": "News API", "domain": "news", "required_env": ["NEWS_API_KEY"], "mode": "real"},
    {"provider_id": "esg_reports", "label": "ESG Reports", "domain": "esg", "required_env": [], "mode": "local_or_remote"},
    {"provider_id": "carbon", "label": "Carbon Data", "domain": "carbon", "required_env": ["CARBON_INTERFACE_API_KEY"], "mode": "real"},
    {"provider_id": "satellite", "label": "Satellite", "domain": "alternative", "required_env": ["NASA_API_KEY"], "mode": "real"},
    {"provider_id": "reddit", "label": "Reddit", "domain": "alternative", "required_env": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"], "mode": "real"},
    {"provider_id": "google_trends", "label": "Google Trends", "domain": "alternative", "required_env": [], "mode": "connector"},
    {"provider_id": "recruiting", "label": "Recruiting", "domain": "alternative", "required_env": ["GREENHOUSE_API_KEY"], "mode": "real"},
    {"provider_id": "patents", "label": "Patents", "domain": "alternative", "required_env": ["USPTO_API_KEY"], "mode": "real"},
]


def build_schema_health(get_client: Callable[[], Any] | None = None) -> dict[str, Any]:
    migration_text = MIGRATION_PATH.read_text(encoding="utf-8") if MIGRATION_PATH.exists() else ""
    remote_probe_enabled = _remote_enabled("SCHEMA_HEALTH_REMOTE_PROBE")
    client = None
    client_backend = "unavailable"
    client_error = None
    if get_client is not None:
        try:
            client = get_client()
            client_backend = getattr(client, "backend", "supabase")
        except Exception as exc:
            client_error = str(exc)

    tables: list[dict[str, Any]] = []
    for spec in REQUIRED_TABLES:
        table_name = spec["table"]
        migration_ready = table_name in migration_text
        probe_status = "not_checked"
        probe_error = None
        remote_ready = False
        if not remote_probe_enabled:
            probe_status = "skipped"
            probe_error = "Remote schema probe is disabled for local/acceptance mode."
        elif client is None:
            probe_status = "degraded"
            probe_error = client_error or "Supabase client is not configured."
        elif client_backend == "in_memory":
            probe_status = "degraded"
            probe_error = "Supabase is not configured; local/in-memory fallback is active."
        else:
            try:
                client.table(table_name).select("*").limit(1).execute()
                remote_ready = True
                probe_status = "ready"
            except Exception as exc:
                probe_status = "blocked"
                probe_error = str(exc)

        if remote_ready:
            status = "ready"
            reason = "Remote Supabase table is queryable."
            missing_fields: list[str] = []
            next_actions: list[str] = []
        elif migration_ready:
            status = "degraded"
            reason = probe_error or "Migration exists locally, but remote schema readiness was not confirmed."
            missing_fields = [] if client_backend != "supabase" else list(spec["required_columns"])
            next_actions = ["Apply database/migrations/006_create_production_ops.sql to Supabase before production cutover."]
        else:
            status = "blocked"
            reason = "Required migration is missing from the repository."
            missing_fields = list(spec["required_columns"])
            next_actions = ["Create the production operations migration before enabling this table."]

        tables.append({
            **spec,
            "status": status,
            "reason": reason,
            "remote_probe_status": probe_status,
            "remote_probe_error": probe_error,
            "migration_ready": migration_ready,
            "migration_file": str(MIGRATION_PATH.relative_to(PROJECT_ROOT)),
            "missing_fields": missing_fields,
            "next_actions": next_actions,
        })

    blocked = sum(1 for row in tables if row["status"] == "blocked")
    degraded = sum(1 for row in tables if row["status"] == "degraded")
    overall = "blocked" if blocked else "degraded" if degraded else "ready"
    return {
        "generated_at": _iso_now(),
        "status": overall,
        "client_backend": client_backend,
        "remote_probe_enabled": remote_probe_enabled,
        "migration_file": str(MIGRATION_PATH.relative_to(PROJECT_ROOT)),
        "summary": {
            "table_count": len(tables),
            "ready": sum(1 for row in tables if row["status"] == "ready"),
            "degraded": degraded,
            "blocked": blocked,
        },
        "tables": tables,
        "next_actions": [] if overall == "ready" else [
            "Run the checked-in migration against Supabase for production.",
            "Keep local fallback enabled for acceptance environments.",
        ],
    }


@dataclass
class JobQueueService:
    get_client: Callable[[], Any] | None = None
    quant_service: Any | None = None

    def __post_init__(self) -> None:
        self.storage = QuantStorageGateway(get_client=self.get_client)

    def queue_health(self) -> dict[str, Any]:
        storage_status = self.storage.status()
        backend = "supabase" if storage_status.get("supabase_ready") else "local_file"
        return {
            "status": "ready" if backend == "supabase" else "degraded",
            "backend": backend,
            "storage_dir": str(self.storage.base_dir / "jobs"),
            "inline_worker_enabled": _env_bool("JOB_INLINE_EXECUTION", True),
            "reason": None if backend == "supabase" else "Supabase is not configured; jobs are persisted under storage/quant/jobs.",
            "next_actions": [] if backend == "supabase" else ["Apply job queue migration and configure Supabase credentials."],
        }

    def list_jobs(self, *, limit: int = 50, status: str | None = None) -> dict[str, Any]:
        normalized_status = str(status or "").strip().lower()
        rows = self.storage.list_records("jobs")
        if _remote_enabled("JOB_QUEUE_REMOTE_WRITE"):
            try:
                remote_rows = list_table_rows("quant_jobs", limit=max(limit, 50), order_by="created_at", desc=True)
                if remote_rows:
                    known = {str(row.get("job_id")) for row in rows}
                    rows.extend(row for row in remote_rows if str(row.get("job_id")) not in known)
            except Exception:
                pass

        if normalized_status:
            rows = [row for row in rows if str(row.get("status") or "").lower() == normalized_status]
        rows = sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
        limited = rows[: max(1, min(int(limit or 50), 200))]
        return {
            "status": self.queue_health()["status"],
            "queue": self.queue_health(),
            "count": len(limited),
            "jobs": _jsonable(limited),
            "reason": None if limited else "No job records are available in the current namespace.",
            "next_actions": [] if limited else ["Create a smoke, data, backtest, or report job from the Job Console."],
        }

    def create_job(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        body = dict(request or {})
        job_type = str(body.get("job_type") or body.get("kind") or body.get("type") or "noop").strip().lower()
        job_id = str(body.get("job_id") or f"job-{uuid.uuid4().hex[:12]}")
        now = _iso_now()
        record = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "payload": body.get("payload") if isinstance(body.get("payload"), dict) else body,
            "result": None,
            "error": None,
            "logs": [],
            "events": [],
            "attempt": 1,
            "acceptance_namespace": body.get("acceptance_namespace") or os.getenv("ACCEPTANCE_NAMESPACE"),
            "created_at": now,
            "updated_at": now,
            "queued_at": now,
            "started_at": None,
            "finished_at": None,
            "runner": "inline_worker" if _env_bool("JOB_INLINE_EXECUTION", True) else "database_queue",
        }
        self._append_event(record, "queued", "queued", {"job_type": job_type})
        self._save_job(record)
        if bool(body.get("run_immediately", _env_bool("JOB_INLINE_EXECUTION", True))):
            record = self._execute_job(record)
        return _jsonable(record)

    def get_job(self, job_id: str) -> dict[str, Any]:
        record = self.storage.load_record("jobs", job_id)
        if record:
            return _jsonable(record)
        row = latest_table_row("quant_jobs", filters={"job_id": job_id})
        if row:
            return _jsonable(row)
        return {
            "job_id": job_id,
            "status": "blocked",
            "reason": "Job record was not found.",
            "missing_config": [],
            "next_actions": ["Check the job id or reset the acceptance namespace."],
        }

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        record = self.get_job(job_id)
        if record.get("status") in TERMINAL_STATUSES:
            record["cancel_status"] = "blocked"
            record["reason"] = "Job is already terminal and cannot be cancelled."
            return _jsonable(record)
        record["status"] = "cancelled"
        record["updated_at"] = _iso_now()
        record["finished_at"] = record["updated_at"]
        self._append_event(record, "cancelled", "cancelled", {"reason": "cancelled_by_api"})
        self._save_job(record)
        return _jsonable(record)

    def retry_job(self, job_id: str) -> dict[str, Any]:
        record = self.get_job(job_id)
        if record.get("status") == "blocked" and record.get("reason") == "Job record was not found.":
            return record
        now = _iso_now()
        record["status"] = "queued"
        record["error"] = None
        record["result"] = None
        record["attempt"] = int(record.get("attempt") or 1) + 1
        record["queued_at"] = now
        record["updated_at"] = now
        record["started_at"] = None
        record["finished_at"] = None
        self._append_event(record, "retry", "queued", {"attempt": record["attempt"]})
        self._save_job(record)
        if _env_bool("JOB_INLINE_EXECUTION", True):
            record = self._execute_job(record)
        return _jsonable(record)

    def job_logs(self, job_id: str) -> dict[str, Any]:
        record = self.get_job(job_id)
        return {
            "job_id": job_id,
            "status": record.get("status"),
            "logs": record.get("logs") or [],
            "events": record.get("events") or [],
        }

    def _execute_job(self, record: dict[str, Any]) -> dict[str, Any]:
        record["status"] = "running"
        record["started_at"] = _iso_now()
        record["updated_at"] = record["started_at"]
        self._append_event(record, "started", "running", {"runner": record.get("runner")})
        self._save_job(record)
        try:
            result = self._dispatch(record["job_type"], record.get("payload") or {})
            terminal_status = self._terminal_status(result)
            record["status"] = terminal_status
            record["result"] = result
            record["error"] = result.get("error") if isinstance(result, dict) else None
            if terminal_status in {"degraded", "blocked"} and isinstance(result, dict):
                record.setdefault("reason", result.get("reason") or result.get("block_reason") or terminal_status)
                record.setdefault("missing_config", result.get("missing_config") or [])
                record.setdefault("next_actions", result.get("next_actions") or [])
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            record["result"] = {
                "status": "failed",
                "reason": str(exc),
                "missing_config": [],
                "next_actions": ["Inspect job logs and retry after fixing the runtime error."],
            }
        record["finished_at"] = _iso_now()
        record["updated_at"] = record["finished_at"]
        self._append_event(record, "finished", record["status"], {"error": record.get("error")})
        self._save_job(record)
        return record

    @staticmethod
    def _terminal_status(result: Any) -> str:
        if not isinstance(result, dict):
            return "succeeded"
        raw = str(result.get("status") or result.get("overall_status") or "succeeded").strip().lower()
        if raw in {"completed", "complete", "success", "ok", "ready"}:
            return "succeeded"
        if raw in JOB_STATUSES:
            return raw
        return "succeeded"

    def _dispatch(self, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        params = dict(payload.get("parameters") or payload.get("payload") or payload)
        if job_type in {"noop", "release_health_smoke"}:
            return {"status": "succeeded", "generated_at": _iso_now(), "message": "Job queue smoke completed."}
        if job_type in {"analysis", "blueprint_analysis", "blueprint_heavy_run"}:
            params.setdefault("family", "technical")
            params.setdefault("symbol", "AAPL")
            params.setdefault("prices", [180, 181.5, 179.2, 183.4, 184.1, 186.2])
            return run_analysis_production(params)
        if job_type in {"model_train", "models_train", "rl_train_cpu_smoke"}:
            params.setdefault("model_key", "job_linear_alpha")
            params.setdefault("X", [[1, 0.2], [0.8, 0.1], [1.2, 0.3]])
            params.setdefault("y", [0.03, 0.018, 0.041])
            return train_model_production(params)
        if job_type in {"model_predict", "models_predict"}:
            params.setdefault("model_key", "job_linear_alpha")
            params.setdefault("X", [[1.0, 0.1]])
            return predict_model_production(params)
        if job_type in {"data_sync", "data_pipeline", "blueprint_data"}:
            params.setdefault("symbols", ["AAPL", "MSFT"])
            params.setdefault("loader", "price_loader")
            return run_data_pipeline_production(params)
        if job_type in {"risk", "risk_evaluate", "blueprint_risk"}:
            params.setdefault("returns", [0.01, -0.02, 0.015, -0.004])
            params.setdefault("nav", [1.0, 0.98, 1.02, 1.01])
            return evaluate_risk_suite_production(params)
        if job_type in {"backtest", "advanced_backtest", "blueprint_backtest"}:
            params.setdefault("returns", [0.01, -0.004, 0.006, 0.002, -0.003, 0.012])
            params.setdefault("notional", 100000)
            return run_advanced_backtest_production(params)
        if job_type in {"infrastructure", "infrastructure_check", "blueprint_infra"}:
            params.setdefault("metrics", {"population_drift": 0.08, "run_cost_usd": 12, "budget_usd": 100})
            return check_infrastructure_production(params)
        if job_type in {"report", "report_generation", "reporting", "blueprint_reporting"}:
            params.setdefault("metrics", {"sharpe": 1.2, "cumulative_return": 0.08})
            result = build_reporting_production(params)
            report_id = f"job-report-{uuid.uuid4().hex[:8]}"
            artifact = {
                "report_id": report_id,
                "generated_at": _iso_now(),
                "html": "<section><h1>Quant Acceptance Report</h1><p>Generated from job queue.</p></section>",
                "payload": result,
            }
            result["artifact"] = self.storage.persist_record("reports", report_id, artifact)
            return result
        if job_type in {"rl_train", "rl_search", "rl_backtest"}:
            return {
                "status": "blocked",
                "reason": "RL long-running worker is not configured in this runtime.",
                "missing_config": ["JOB_WORKER_ENABLED or external RL worker"],
                "next_actions": ["Enable a job worker with Quant RL dependencies, or run CPU smoke via job_type=rl_train_cpu_smoke."],
            }
        return {
            "status": "degraded",
            "reason": f"Unsupported job_type '{job_type}' was persisted but not executed.",
            "missing_config": [],
            "next_actions": ["Register this job type in gateway.platform.production_ops.JobQueueService._dispatch."],
        }

    def _append_event(self, record: dict[str, Any], event_type: str, status: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "event_id": f"job-event-{uuid.uuid4().hex[:12]}",
            "job_id": record.get("job_id"),
            "event_type": event_type,
            "status": status,
            "payload": payload or {},
            "created_at": _iso_now(),
        }
        record.setdefault("events", []).append(event)
        record.setdefault("logs", []).append(f"{event['created_at']} {event_type} {status}")
        try:
            if _remote_enabled("JOB_QUEUE_REMOTE_WRITE"):
                save_table_row("quant_job_events", event)
        except Exception:
            pass
        try:
            self.storage.persist_record("job_events", event["event_id"], event)
        except Exception:
            pass

    def _save_job(self, record: dict[str, Any]) -> None:
        payload = _jsonable(record)
        payload["storage"] = self.storage.persist_record("jobs", record["job_id"], payload)
        try:
            if _remote_enabled("JOB_QUEUE_REMOTE_WRITE"):
                updated = update_table_row("quant_jobs", payload, match={"job_id": record["job_id"]})
                if not updated:
                    save_table_row("quant_jobs", payload)
        except Exception:
            pass


@dataclass
class DataConfigCenterService:
    get_client: Callable[[], Any] | None = None

    def __post_init__(self) -> None:
        self.storage = QuantStorageGateway(get_client=self.get_client)

    def get_config_center(self) -> dict[str, Any]:
        saved = {
            str(row.get("provider_id") or row.get("record_id") or ""): row
            for row in self.storage.list_records("data_source_configs")
            if isinstance(row, dict)
        }
        providers = [self._provider_status(spec, saved.get(spec["provider_id"])) for spec in PROVIDER_SPECS]
        degraded = sum(1 for item in providers if item["status"] == "degraded")
        blocked = sum(1 for item in providers if item["status"] == "blocked")
        storage_status = self.storage.status()
        status = "blocked" if blocked else "degraded" if degraded or not storage_status.get("supabase_ready") else "ready"
        return {
            "generated_at": _iso_now(),
            "status": status,
            "reason": None if status == "ready" else "Some providers are missing configuration or are using local fallback.",
            "storage": storage_status,
            "provider_count": len(providers),
            "providers": providers,
            "health_checks": self.storage.list_records("provider_health_checks")[:50],
            "quality_runs": self.storage.list_records("data_quality_runs")[:50],
            "next_actions": [] if status == "ready" else [
                "Configure missing API keys in the runtime environment.",
                "Apply data_source_configs/provider_health_checks/data_quality_runs migrations for production.",
            ],
        }

    def save_provider_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = dict(payload or {})
        provider_id = str(body.get("provider_id") or body.get("provider") or "").strip().lower()
        if not provider_id:
            return {
                "status": "blocked",
                "reason": "provider_id is required.",
                "missing_config": ["provider_id"],
                "next_actions": ["Submit a provider_id such as alpaca_paper or fred."],
            }
        if body.get("api_key"):
            body["api_key_masked"] = _mask_secret(str(body.get("api_key")))
            body.pop("api_key", None)
        now = _iso_now()
        record = {
            "provider_id": provider_id,
            "priority": int(body.get("priority") or 100),
            "status": str(body.get("status") or "configured").lower(),
            "payload": body,
            "created_at": body.get("created_at") or now,
            "updated_at": now,
            "acceptance_namespace": body.get("acceptance_namespace") or os.getenv("ACCEPTANCE_NAMESPACE"),
        }
        record["storage"] = self.storage.persist_record("data_source_configs", provider_id, record)
        try:
            if _remote_enabled("DATA_CONFIG_REMOTE_WRITE"):
                updated = update_table_row("data_source_configs", record, match={"provider_id": provider_id})
                if not updated:
                    save_table_row("data_source_configs", record)
        except Exception:
            pass
        record["status"] = "degraded" if not self.storage.status().get("supabase_ready") else "ready"
        record["reason"] = None if record["status"] == "ready" else "Saved locally because Supabase table is unavailable."
        record["next_actions"] = [] if record["status"] == "ready" else ["Apply data config migration to Supabase for production persistence."]
        return _jsonable(record)

    @staticmethod
    def _provider_status(spec: dict[str, Any], saved_config: dict[str, Any] | None = None) -> dict[str, Any]:
        required = list(spec.get("required_env") or [])
        missing = [name for name in required if not os.getenv(name)]
        saved_payload = (saved_config or {}).get("payload") if isinstance(saved_config, dict) else {}
        configured = not missing or bool(saved_payload)
        status = "ready" if configured else "degraded"
        source_mode = spec["mode"] if configured else "local_fallback"
        synthetic_allowed = _env_bool("ALLOW_SYNTHETIC_DATA", False)
        return {
            **spec,
            "status": status,
            "configured": configured,
            "missing_config": missing,
            "source_mode": source_mode,
            "freshness": "runtime_checked" if configured else "not_checked",
            "lineage": "tracked",
            "quality_score": 0.9 if configured else 0.35,
            "data_classification": "synthetic_allowed" if synthetic_allowed and not configured else "real_or_cached",
            "saved_config": bool(saved_config),
            "reason": None if configured else "Provider is missing API configuration; UI must show degraded instead of fake success.",
            "next_actions": [] if configured else [f"Set {name}" for name in missing] or ["Install/configure provider dependency."],
        }


def build_trading_safety_center(quant_service: Any | None = None, trading_service: Any | None = None) -> dict[str, Any]:
    generated_at = _iso_now()
    controls: dict[str, Any] = {}
    paper_account: dict[str, Any] = {}
    live_account: dict[str, Any] = {}
    calendar: dict[str, Any] = {}
    submit_locks: dict[str, Any] = {"locks": []}
    latest_evidence: dict[str, Any] | None = None
    warnings: list[str] = []

    if quant_service is not None:
        for label, fn in [
            ("controls", lambda: quant_service.get_execution_controls()),
            ("paper_account", lambda: quant_service.get_execution_account(broker="alpaca", mode="paper")),
            ("live_account", lambda: quant_service.get_execution_account(broker="alpaca", mode="live")),
            ("calendar", lambda: quant_service.get_trading_calendar_status()),
            ("submit_locks", lambda: quant_service.list_submit_locks(limit=20)),
            ("latest_evidence", lambda: quant_service.latest_session_evidence()),
        ]:
            try:
                value = fn()
                if label == "controls":
                    controls = value or {}
                elif label == "paper_account":
                    paper_account = value or {}
                elif label == "live_account":
                    live_account = value or {}
                elif label == "calendar":
                    calendar = value or {}
                elif label == "submit_locks":
                    submit_locks = value or submit_locks
                elif label == "latest_evidence":
                    latest_evidence = value
            except Exception as exc:
                warnings.append(f"{label}: {exc}")
    else:
        warnings.append("Quant service is not initialized.")

    autopilot: dict[str, Any] = {}
    if trading_service is not None and hasattr(trading_service, "get_autopilot_policy"):
        try:
            autopilot = trading_service.get_autopilot_policy() or {}
        except Exception as exc:
            warnings.append(f"autopilot_policy: {exc}")

    scheduler_auto_submit = _env_bool("SCHEDULER_AUTO_SUBMIT", False)
    unattended_paper = _env_bool("UNATTENDED_PAPER_MODE", False)
    paper_ready = bool(paper_account.get("paper_ready") or paper_account.get("connected"))
    market_open = bool(calendar.get("is_open") or calendar.get("market_open"))
    require_session = bool(getattr(settings, "SCHEDULER_REQUIRE_TRADING_SESSION", True))
    kill_switch = bool(controls.get("kill_switch_enabled"))
    risk_gate_ok = not kill_switch
    paper_allowed = scheduler_auto_submit and unattended_paper and paper_ready and (market_open or not require_session) and risk_gate_ok
    blockers = []
    if not scheduler_auto_submit:
        blockers.append("SCHEDULER_AUTO_SUBMIT=false")
    if not unattended_paper:
        blockers.append("UNATTENDED_PAPER_MODE=false")
    if not paper_ready:
        blockers.append("alpaca_paper_broker_not_ready")
    if require_session and not market_open:
        blockers.append("market_session_closed")
    if kill_switch:
        blockers.append("kill_switch_enabled")

    status = "ready" if paper_allowed else "degraded"
    if not quant_service:
        status = "blocked"

    return {
        "generated_at": generated_at,
        "status": status,
        "mode": "paper",
        "live_auto_submit": {
            "allowed": False,
            "reason": "Live auto-submit disabled by hard rule.",
            "proof": "This endpoint never returns a live submission permit; live routes may only produce plans or recommendations.",
        },
        "paper_auto_submit": {
            "allowed": paper_allowed,
            "scheduler_auto_submit": scheduler_auto_submit,
            "unattended_paper_mode": unattended_paper,
            "broker_ready": paper_ready,
            "market_open": market_open,
            "risk_gate_ok": risk_gate_ok,
            "blockers": blockers,
        },
        "kill_switch": {
            "enabled": kill_switch,
            "reason": controls.get("kill_switch_reason") or "",
        },
        "autopilot": autopilot,
        "broker_readiness": {
            "paper": paper_account,
            "live": live_account,
        },
        "risk_gate": {
            "status": "pass" if risk_gate_ok else "blocked",
            "reason": "Kill switch is clear." if risk_gate_ok else "Kill switch is enabled.",
        },
        "submit_locks": submit_locks,
        "latest_submit_decision_trace": latest_evidence,
        "warnings": warnings,
        "reason": None if status == "ready" else "Paper auto-submit gate is not fully armed.",
        "missing_config": blockers,
        "next_actions": [] if paper_allowed else [
            "Confirm Paper mode only.",
            "Configure Alpaca Paper credentials.",
            "Enable SCHEDULER_AUTO_SUBMIT and UNATTENDED_PAPER_MODE only after acceptance sign-off.",
        ],
    }


def build_automation_timeline(quant_service: Any | None = None) -> dict[str, Any]:
    fixed_order = ["preopen", "workflow", "risk_gate", "paper_plan", "paper_submit", "broker_sync", "outcomes", "report"]
    if quant_service is None:
        return {
            "generated_at": _iso_now(),
            "status": "blocked",
            "reason": "Quant service is not initialized.",
            "missing_config": ["quant_service"],
            "next_actions": ["Start the API with QuantSystem enabled."],
            "stages": [
                {"stage": stage, "status": "blocked", "reason": "quant_service_missing"}
                for stage in fixed_order
            ],
        }
    try:
        evidence = quant_service.latest_session_evidence() or {}
    except Exception as exc:
        evidence = {}
        error = str(exc)
    else:
        error = None
    stage_payloads = evidence.get("stages") if isinstance(evidence, dict) else {}
    stage_payloads = stage_payloads or {}
    aliases = {
        "workflow": ["workflow", "hybrid_workflow"],
        "risk_gate": ["risk_gate", "paper_gate", "validation"],
        "paper_plan": ["paper_plan", "execution_plan"],
        "report": ["report", "digest", "promotion", "snapshot", "backup"],
    }
    stages = []
    missing = []
    for stage in fixed_order:
        candidates = aliases.get(stage, [stage])
        payload = next((stage_payloads.get(name) for name in candidates if stage_payloads.get(name)), None)
        if payload:
            stages.append({
                "stage": stage,
                "status": payload.get("status") or "completed",
                "input_summary": payload.get("input_summary") or payload.get("stage"),
                "output_summary": payload.get("output_summary") or payload.get("status"),
                "duration_seconds": payload.get("duration_seconds"),
                "error": payload.get("error"),
                "artifacts": payload.get("artifacts") or {},
                "last_run_at": payload.get("finished_at") or payload.get("started_at"),
                "blockers": payload.get("blockers") or [],
                "warnings": payload.get("warnings") or [],
            })
        else:
            missing.append(stage)
            stages.append({
                "stage": stage,
                "status": "degraded",
                "reason": "No latest session evidence for this stage.",
                "input_summary": None,
                "output_summary": None,
                "duration_seconds": None,
                "error": None,
                "artifacts": {},
                "last_run_at": None,
                "blockers": [],
                "warnings": [],
            })
    try:
        recent_events = quant_service.storage.list_records("scheduler_events")[:50]
    except Exception:
        recent_events = []
    status = "ready" if not missing else "degraded"
    return {
        "generated_at": _iso_now(),
        "status": status,
        "session_date": evidence.get("session_date") if isinstance(evidence, dict) else None,
        "latest_evidence": evidence or None,
        "missing_stages": missing,
        "stages": stages,
        "recent_events": recent_events,
        "reason": None if status == "ready" else (error or "Latest automation evidence is incomplete."),
        "missing_config": [] if not error else ["session_evidence"],
        "next_actions": [] if status == "ready" else [
            "Run preopen analysis, workflow, broker sync, outcome settlement, and report generation.",
            "Check scheduler heartbeat and paper gate blockers.",
        ],
    }


def build_release_health(
    *,
    get_client: Callable[[], Any] | None = None,
    quant_service: Any | None = None,
    trading_service: Any | None = None,
) -> dict[str, Any]:
    schema = build_schema_health(get_client=get_client)
    jobs = JobQueueService(get_client=get_client, quant_service=quant_service).queue_health()
    data = DataConfigCenterService(get_client=get_client).get_config_center()
    safety = build_trading_safety_center(quant_service=quant_service, trading_service=trading_service)
    frontend_dist = PROJECT_ROOT / "dist" / "app"
    e2e_spec = PROJECT_ROOT / "e2e" / "full-app-acceptance.spec.js"
    checks = {
        "api": {"status": "ready", "endpoint": "/livez"},
        "frontend": {
            "status": "ready" if frontend_dist.exists() else "degraded",
            "dist_path": str(frontend_dist),
            "reason": None if frontend_dist.exists() else "Static frontend has not been built yet.",
        },
        "schema": schema,
        "job_queue": jobs,
        "data_config": data,
        "trading_safety": safety,
        "e2e_acceptance": {
            "status": "ready" if e2e_spec.exists() else "blocked",
            "spec": str(e2e_spec.relative_to(PROJECT_ROOT)),
            "artifact_dir": "test-results/playwright/full-app-acceptance",
        },
    }
    statuses = [
        checks["frontend"]["status"],
        schema["status"],
        jobs["status"],
        data["status"],
        safety["status"],
        checks["e2e_acceptance"]["status"],
    ]
    overall = "blocked" if "blocked" in statuses else "degraded" if "degraded" in statuses else "ready"
    return {
        "generated_at": _iso_now(),
        "status": overall,
        "checks": checks,
        "next_actions": [] if overall == "ready" else [
            "Run scripts/release_health_check.py against a local API.",
            "Apply Supabase migrations before production cutover.",
            "Run npx playwright test e2e/full-app-acceptance.spec.js and review artifacts.",
        ],
    }
