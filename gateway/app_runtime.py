from __future__ import annotations

import asyncio
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import FastAPI, HTTPException

from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def _optional_import(module_path: str, names: tuple[str, ...], label: str) -> list[Any]:
    try:
        module = importlib.import_module(module_path)
        return [getattr(module, name) for name in names]
    except Exception as exc:
        logging.getLogger(__name__).warning(f"{label}模块加载失败: {exc}")
        return [None for _ in names]


@dataclass
class RuntimeContext:
    get_query_engine: Any = None
    save_message: Any = None
    get_history: Any = None
    create_session: Any = None
    get_client: Any = None
    get_orchestrator: Any = None
    run_agent: Any = None
    ESGScoringFramework: Any = None
    ESGScoreReport: Any = None
    ESGVisualizer: Any = None
    DataSourceManager: Any = None
    CompanyData: Any = None
    ESGReportGenerator: Any = None
    ReportScheduler: Any = None
    PushRule: Any = None
    ReportSubscription: Any = None
    esg_scorer: Any = None
    esg_visualizer: Any = None
    data_source_manager: Any = None
    report_generator: Any = None
    report_scheduler: Any = None
    report_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    sync_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ensure_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        if session_id and self.create_session is not None:
            self.create_session(session_id=session_id, user_id=user_id)

    def serialize_model(self, model: Any) -> Any:
        if model is None:
            return None
        if hasattr(model, "model_dump"):
            return model.model_dump()
        if hasattr(model, "dict"):
            return model.dict()
        return model

    def flatten_report_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = row.get("data") or {}
        if not isinstance(payload, dict):
            payload = {}

        report_id = row.get("id") or payload.get("report_id")
        flattened = dict(payload)
        flattened["report_id"] = report_id
        flattened.setdefault("id", report_id)
        flattened.setdefault("report_type", row.get("report_type"))
        flattened.setdefault("title", row.get("title"))
        flattened.setdefault("period_start", row.get("period_start"))
        flattened.setdefault("period_end", row.get("period_end"))
        flattened.setdefault("generated_at", row.get("generated_at"))
        return flattened

    def fetch_report_row(self, report_id: str) -> Optional[dict[str, Any]]:
        if self.get_client is None:
            return None

        response = (
            self.get_client()
            .table("esg_reports")
            .select("id, report_type, title, period_start, period_end, data, generated_at")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def fetch_latest_report_row(
        self,
        report_type: str,
        company: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if self.get_client is None:
            return None

        response = (
            self.get_client()
            .table("esg_reports")
            .select("id, report_type, title, period_start, period_end, data, generated_at")
            .eq("report_type", report_type)
            .order("generated_at", desc=True)
            .limit(20)
            .execute()
        )

        for row in response.data or []:
            payload = row.get("data") or {}
            analyses = payload.get("company_analyses") or []
            if not company:
                return row
            if any(str(item.get("company_name", "")).lower() == company.lower() for item in analyses):
                return row

        return None

    def generate_report_by_type(self, report_type: str, companies: list[str]):
        if self.report_generator is None:
            raise HTTPException(status_code=503, detail="Report Generator not ready")

        if report_type == "daily":
            return self.report_generator.generate_daily_report(companies)
        if report_type == "weekly":
            return self.report_generator.generate_weekly_report(companies)
        if report_type == "monthly":
            return self.report_generator.generate_monthly_report(companies)
        raise HTTPException(status_code=400, detail="Invalid report type")

    def store_report_job(
        self,
        job_id: str,
        report: Any,
        persisted_id: Optional[str] = None,
    ) -> dict[str, Any]:
        payload = self.serialize_model(report) or {}
        payload["report_id"] = persisted_id or job_id
        payload.setdefault("id", persisted_id or job_id)

        self.report_jobs[job_id] = {
            "status": "completed",
            "report_id": persisted_id or job_id,
            "report": payload,
            "generated_at": payload.get("generated_at"),
        }
        return payload

    def get_scheduler_statistics(self, days: int = 7) -> dict[str, Any]:
        try:
            orchestrator = self.get_orchestrator() if self.get_orchestrator else None
        except Exception as exc:
            logger.warning(f"Scheduler orchestrator unavailable: {exc}")
            orchestrator = None

        if orchestrator is None:
            return {
                "period_days": days,
                "total_scans": 0,
                "success_rate": 0,
                "last_sync_time": None,
                "degraded": True,
                "message": "Scheduler not ready",
            }

        try:
            stats = orchestrator.get_pipeline_statistics(days=days) or {}
        except Exception as exc:
            logger.warning(f"Scheduler statistics unavailable: {exc}")
            return {
                "period_days": days,
                "total_scans": 0,
                "success_rate": 0,
                "last_sync_time": None,
                "degraded": True,
                "message": "Scheduler statistics unavailable",
            }

        return {
            "period_days": days,
            "total_scans": stats.get("total_scans", stats.get("scan_count", 0)),
            "success_rate": stats.get("success_rate", 0),
            "last_sync_time": stats.get("last_sync_time"),
            "statistics": stats,
        }

    async def startup(self, app: FastAPI) -> None:
        logger.info("[Startup] Initializing ESG enhanced modules...")

        if getattr(app.state, "query_engine", None) is None:
            app.state.query_engine = None
            if self.get_query_engine is not None:
                async def _init_rag():
                    loop = asyncio.get_running_loop()
                    try:
                        engine = await loop.run_in_executor(None, self.get_query_engine)
                        app.state.query_engine = engine
                        logger.info("[Startup] RAG engine ready (background init complete)")
                    except Exception as exc:
                        logger.warning(f"[Startup] RAG engine failed: {exc}")

                asyncio.create_task(_init_rag())
                logger.info("[Startup] RAG engine building in background, server starting now...")
            else:
                logger.warning("[Startup] RAG engine skipped (module not available)")

        if self.esg_scorer is None and self.ESGScoringFramework is not None:
            try:
                self.esg_scorer = self.ESGScoringFramework()
                logger.info("[Startup] ESG Scorer initialized")
            except Exception as exc:
                logger.warning(f"[Startup] ESG Scorer failed: {exc}")

        if self.esg_visualizer is None and self.ESGVisualizer is not None:
            try:
                self.esg_visualizer = self.ESGVisualizer()
                logger.info("[Startup] ESG Visualizer initialized")
            except Exception as exc:
                logger.warning(f"[Startup] ESG Visualizer failed: {exc}")

        if self.data_source_manager is None and self.DataSourceManager is not None:
            try:
                self.data_source_manager = self.DataSourceManager()
                logger.info("[Startup] Data Source Manager initialized")
            except Exception as exc:
                logger.warning(f"[Startup] Data Source Manager failed: {exc}")

        if self.report_generator is None and self.ESGReportGenerator is not None:
            try:
                self.report_generator = self.ESGReportGenerator()
                logger.info("[Startup] Report Generator initialized")
            except Exception as exc:
                logger.warning(f"[Startup] Report Generator failed: {exc}")

        if self.report_scheduler is None and self.ReportScheduler is not None:
            try:
                self.report_scheduler = self.ReportScheduler()
                self.report_scheduler.start_background_scheduler()
                logger.info("[Startup] Report Scheduler started")
            except Exception as exc:
                logger.warning(f"[Startup] Report Scheduler failed: {exc}")

        logger.info("[Startup] All modules initialized successfully")


def build_runtime() -> RuntimeContext:
    get_query_engine, = _optional_import(
        "gateway.rag.rag_main",
        ("get_query_engine",),
        "RAG",
    )
    save_message, get_history, create_session, get_client = _optional_import(
        "gateway.db.supabase_client",
        ("save_message", "get_history", "create_session", "get_client"),
        "Supabase",
    )
    get_orchestrator, = _optional_import(
        "gateway.scheduler.orchestrator",
        ("get_orchestrator",),
        "Orchestrator",
    )
    run_agent, = _optional_import(
        "gateway.agents.graph",
        ("run_agent",),
        "Agent graph",
    )
    ESGScoringFramework, ESGScoreReport = _optional_import(
        "gateway.agents.esg_scorer",
        ("ESGScoringFramework", "ESGScoreReport"),
        "ESG scorer",
    )
    ESGVisualizer, = _optional_import(
        "gateway.agents.esg_visualizer",
        ("ESGVisualizer",),
        "ESG visualizer",
    )
    DataSourceManager, CompanyData = _optional_import(
        "gateway.scheduler.data_sources",
        ("DataSourceManager", "CompanyData"),
        "DataSource",
    )
    ESGReportGenerator, = _optional_import(
        "gateway.scheduler.report_generator",
        ("ESGReportGenerator",),
        "ReportGenerator",
    )
    ReportScheduler, PushRule, ReportSubscription = _optional_import(
        "gateway.scheduler.report_scheduler",
        ("ReportScheduler", "PushRule", "ReportSubscription"),
        "ReportScheduler",
    )

    return RuntimeContext(
        get_query_engine=get_query_engine,
        save_message=save_message,
        get_history=get_history,
        create_session=create_session,
        get_client=get_client,
        get_orchestrator=get_orchestrator,
        run_agent=run_agent,
        ESGScoringFramework=ESGScoringFramework,
        ESGScoreReport=ESGScoreReport,
        ESGVisualizer=ESGVisualizer,
        DataSourceManager=DataSourceManager,
        CompanyData=CompanyData,
        ESGReportGenerator=ESGReportGenerator,
        ReportScheduler=ReportScheduler,
        PushRule=PushRule,
        ReportSubscription=ReportSubscription,
    )


runtime = build_runtime()
