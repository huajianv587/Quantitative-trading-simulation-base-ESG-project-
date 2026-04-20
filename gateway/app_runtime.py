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
    quant_system: Any = None
    trading_service: Any = None
    report_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    sync_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _ensure_runtime_service(
        self,
        *,
        instance_attr: str,
        class_attr: str,
        label: str,
        post_init: Any | None = None,
    ) -> Any:
        existing = getattr(self, instance_attr, None)
        if existing is not None:
            return existing

        cls = getattr(self, class_attr, None)
        if cls is None:
            return None

        try:
            instance = cls()
            if post_init is not None:
                post_init(instance)
            setattr(self, instance_attr, instance)
            logger.info(f"[Runtime] {label} initialized")
            return instance
        except Exception as exc:
            logger.warning(f"[Runtime] {label} init failed: {exc}")
            return None

    def ensure_optional_services(self, *, start_scheduler: bool = False) -> dict[str, bool]:
        scorer = self._ensure_runtime_service(
            instance_attr="esg_scorer",
            class_attr="ESGScoringFramework",
            label="ESG Scorer",
        )
        visualizer = self._ensure_runtime_service(
            instance_attr="esg_visualizer",
            class_attr="ESGVisualizer",
            label="ESG Visualizer",
        )
        data_source_manager = self._ensure_runtime_service(
            instance_attr="data_source_manager",
            class_attr="DataSourceManager",
            label="Data Source Manager",
        )
        report_generator = self._ensure_runtime_service(
            instance_attr="report_generator",
            class_attr="ESGReportGenerator",
            label="Report Generator",
        )

        report_scheduler = getattr(self, "report_scheduler", None)
        if report_scheduler is None:
            report_scheduler = self._ensure_runtime_service(
                instance_attr="report_scheduler",
                class_attr="ReportScheduler",
                label="Report Scheduler",
            )

        if (
            start_scheduler
            and report_scheduler is not None
            and hasattr(report_scheduler, "start_background_scheduler")
            and not bool(getattr(report_scheduler, "is_running", False))
        ):
            try:
                report_scheduler.start_background_scheduler()
                logger.info("[Runtime] Report Scheduler background loop started")
            except Exception as exc:
                logger.warning(f"[Runtime] Report Scheduler start failed: {exc}")

        return {
            "esg_scorer": scorer is not None,
            "esg_visualizer": visualizer is not None,
            "data_source_manager": data_source_manager is not None,
            "report_generator": report_generator is not None,
            "report_scheduler": report_scheduler is not None,
        }

    def ensure_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        if session_id and self.create_session is not None:
            try:
                self.create_session(session_id=session_id, user_id=user_id)
            except Exception as exc:
                logger.warning(f"Session initialization skipped: {exc}")

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
        if self.get_client is not None:
            response = (
                self.get_client()
                .table("esg_reports")
                .select("id, report_type, title, period_start, period_end, data, generated_at")
                .eq("id", report_id)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]

        memory_job = self.report_jobs.get(report_id)
        if not memory_job or not memory_job.get("report"):
            return None

        report = dict(memory_job["report"])
        return {
            "id": report.get("report_id") or report.get("id") or report_id,
            "report_type": report.get("report_type"),
            "title": report.get("title"),
            "period_start": report.get("period_start"),
            "period_end": report.get("period_end"),
            "data": report,
            "generated_at": report.get("generated_at"),
        }

    def fetch_latest_report_row(
        self,
        report_type: str,
        company: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if self.get_client is not None:
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

        memory_rows = []
        for job_id, job in self.report_jobs.items():
            payload = job.get("report") or {}
            if not payload:
                continue
            if report_type and payload.get("report_type") != report_type:
                continue
            analyses = payload.get("company_analyses") or []
            if company and not any(str(item.get("company_name", "")).lower() == company.lower() for item in analyses):
                continue
            memory_rows.append({
                "id": payload.get("report_id") or payload.get("id") or job_id,
                "report_type": payload.get("report_type"),
                "title": payload.get("title"),
                "period_start": payload.get("period_start"),
                "period_end": payload.get("period_end"),
                "data": payload,
                "generated_at": payload.get("generated_at"),
            })

        if not memory_rows:
            return None

        memory_rows.sort(key=lambda row: row.get("generated_at") or "", reverse=True)
        return memory_rows[0]

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

        self.ensure_optional_services(start_scheduler=True)

        if self.quant_system is not None and self.trading_service is None:
            try:
                from gateway.trading.service import get_trading_service

                self.trading_service = get_trading_service(
                    quant_system=self.quant_system,
                    get_client=self.get_client,
                )
                logger.info("[Runtime] Trading agent service initialized")
            except Exception as exc:
                logger.warning(f"[Runtime] Trading agent service init failed: {exc}")

        if self.trading_service is not None and hasattr(self.trading_service, "startup"):
            try:
                await self.trading_service.startup()
                logger.info("[Runtime] Trading agent service started")
            except Exception as exc:
                logger.warning(f"[Runtime] Trading agent service startup failed: {exc}")

        logger.info("[Startup] All modules initialized successfully")

    async def shutdown(self, app: FastAPI) -> None:
        if self.trading_service is not None and hasattr(self.trading_service, "shutdown"):
            try:
                await self.trading_service.shutdown()
                logger.info("[Runtime] Trading agent service stopped")
            except Exception as exc:
                logger.warning(f"[Runtime] Trading agent service shutdown failed: {exc}")


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
    get_quant_system, = _optional_import(
        "gateway.quant.service",
        ("get_quant_system",),
        "QuantSystem",
    )

    quant_system = None
    if get_quant_system is not None:
        try:
            quant_system = get_quant_system(get_client=get_client)
        except Exception as exc:
            logger.warning(f"Quant system init failed: {exc}")

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
        quant_system=quant_system,
    )


runtime = build_runtime()
