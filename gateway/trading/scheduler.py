from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from gateway.config import settings

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
    from apscheduler.triggers.cron import CronTrigger  # type: ignore
except Exception:  # pragma: no cover - local fallback when APScheduler is not installed yet.
    class CronTrigger:  # type: ignore
        def __init__(self, *, day_of_week: str, hour: int, minute: int, timezone: str):
            self.day_of_week = day_of_week
            self.hour = hour
            self.minute = minute
            self.timezone = timezone

    class _FallbackJob:
        def __init__(self, job_id: str, func: Callable[[], Awaitable[Any]], trigger: CronTrigger, name: str):
            self.id = job_id
            self.func = func
            self.trigger = trigger
            self.name = name
            self.next_run_time = None

    class AsyncIOScheduler:  # type: ignore
        def __init__(self, timezone: str):
            self.timezone = timezone
            self._jobs: dict[str, _FallbackJob] = {}
            self.running = False

        def add_job(self, func: Callable[[], Awaitable[Any]], trigger: CronTrigger, id: str, name: str, replace_existing: bool = True):
            self._jobs[id] = _FallbackJob(id, func, trigger, name)

        def get_jobs(self):
            return list(self._jobs.values())

        def start(self):
            self.running = True

        def shutdown(self, wait: bool = False):
            self.running = False


class TradingScheduler:
    JOB_SPECS = {
        "premarket_agent": {"hour": 8, "minute": 30, "label": "Premarket Agent"},
        "intraday_monitor_start": {"hour": 9, "minute": 30, "label": "Start Intraday Monitor"},
        "paper_reward_candidates_run": {"hour": 10, "minute": 0, "label": "Paper Reward Candidates"},
        "midday_summary_agent": {"hour": 11, "minute": 30, "label": "Midday Summary"},
        "intraday_monitor_stop": {"hour": 15, "minute": 0, "label": "Stop Intraday Monitor"},
        "review_agent": {"hour": 21, "minute": 30, "label": "Daily Review"},
        "paper_reward_settlement": {"hour": 21, "minute": 45, "label": "Paper Reward Settlement"},
    }

    def __init__(self, run_job: Callable[[str, str | None], Awaitable[dict[str, Any]]]) -> None:
        self.timezone = getattr(settings, "SCHEDULER_TIMEZONE", "America/New_York") or "America/New_York"
        self._run_job = run_job
        self._scheduler = AsyncIOScheduler(timezone=self.timezone)
        self._configured = False

    def start(self) -> None:
        if self._configured:
            if not getattr(self._scheduler, "running", False):
                self._scheduler.start()
            return
        for job_name, spec in self.JOB_SPECS.items():
            trigger = CronTrigger(
                day_of_week="mon-fri",
                hour=int(spec["hour"]),
                minute=int(spec["minute"]),
                timezone=self.timezone,
            )
            self._scheduler.add_job(
                self._build_runner(job_name),
                trigger=trigger,
                id=job_name,
                name=str(spec["label"]),
                replace_existing=True,
            )
        self._scheduler.start()
        self._configured = True

    async def shutdown(self) -> None:
        if getattr(self._scheduler, "running", False):
            self._scheduler.shutdown(wait=False)

    def status(self) -> dict[str, Any]:
        jobs = []
        for job in self._scheduler.get_jobs():
            spec = self.JOB_SPECS.get(job.id, {})
            jobs.append(
                {
                    "job_name": job.id,
                    "label": getattr(job, "name", spec.get("label", job.id)),
                    "schedule": f"mon-fri {int(spec.get('hour', 0)):02d}:{int(spec.get('minute', 0)):02d}",
                    "timezone": self.timezone,
                    "next_run_time": self._serialize_dt(getattr(job, "next_run_time", None)),
                }
            )
        return {
            "timezone": self.timezone,
            "running": bool(getattr(self._scheduler, "running", False)),
            "job_count": len(jobs),
            "jobs": jobs,
        }

    async def run_now(self, job_name: str) -> dict[str, Any]:
        if job_name not in self.JOB_SPECS:
            raise ValueError(f"Unknown trading job: {job_name}")
        return await self._run_job(job_name, None)

    def _build_runner(self, job_name: str):
        async def _runner():
            await self._run_job(job_name, datetime.now(timezone.utc).isoformat())

        return _runner

    @staticmethod
    def _serialize_dt(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        return str(value)
