from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from gateway.db.supabase_client import get_client
from gateway.rag.event_indexer import index_events_async
from gateway.scheduler.event_extractor import get_extractor
from gateway.scheduler.matcher import get_matcher
from gateway.scheduler.notifier import get_notifier
from gateway.scheduler.risk_scorer import get_risk_scorer
from gateway.scheduler.scanner import get_scanner
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerOrchestrator:
    """Coordinate scanner -> extractor -> scorer -> matcher -> notifier."""

    def __init__(self):
        self.scanner = get_scanner()
        self.extractor = get_extractor()
        self.matcher = get_matcher()
        self.risk_scorer = get_risk_scorer()
        self.notifier = get_notifier()
        self.db = get_client()

    def run_full_pipeline(self) -> dict:
        logger.info("=" * 80)
        logger.info("[Orchestrator] Starting full pipeline execution...")
        logger.info("=" * 80)

        pipeline_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stages": {},
            "status": "success",
            "errors": [],
        }

        try:
            logger.info("[Orchestrator] Stage 1/5: Scanning for new events...")
            scan_result = self.scanner.run_scan()
            pipeline_result["stages"]["scan"] = scan_result

            if not scan_result.get("saved_events", 0):
                logger.info("[Orchestrator] No new events found, exiting pipeline.")
                return pipeline_result

            event_ids = scan_result.get("event_ids", [])
            logger.info(f"[Orchestrator] Found {len(event_ids)} new events")

            logger.info("[Orchestrator] Stage 2/5: Extracting structured information...")
            extract_result = self.extractor.process_new_events(event_ids)
            pipeline_result["stages"]["extract"] = extract_result

            if not extract_result.get("saved", 0):
                logger.warning("[Orchestrator] No events extracted successfully")
                pipeline_result["status"] = "partial"

            extracted_ids = extract_result.get("saved_ids", [])
            logger.info(f"[Orchestrator] Extracted {len(extracted_ids)} events")

            if extracted_ids:
                index_events_async(extracted_ids)

            logger.info("[Orchestrator] Stage 3/5: Scoring risk levels...")
            score_result = self.risk_scorer.score_batch_events(extracted_ids)
            pipeline_result["stages"]["risk_score"] = score_result
            logger.info(f"[Orchestrator] Scored {score_result.get('scored', 0)} events")

            logger.info("[Orchestrator] Stage 4/5: Matching events to users...")
            match_result = self.matcher.match_batch_events(extracted_ids)
            pipeline_result["stages"]["match"] = match_result
            total_matches = match_result.get("total_matches", 0)
            logger.info(f"[Orchestrator] Matched {total_matches} event-user pairs")

            logger.info("[Orchestrator] Stage 5/5: Sending notifications...")
            notify_result = {
                "total_events": len(extracted_ids),
                "total_notifications": 0,
                "by_event": [],
            }
            for event_id in extracted_ids:
                event_matches = next(
                    (item for item in match_result.get("results", []) if item.get("event_id") == event_id),
                    None,
                )
                if not event_matches:
                    continue
                matched_users = event_matches.get("matched_users", [])
                if not matched_users:
                    continue
                notification_result = self.notifier.send_notifications(event_id, matched_users)
                notify_result["by_event"].append({"event_id": event_id, **notification_result})
                notify_result["total_notifications"] += notification_result.get("sent", 0)

            pipeline_result["stages"]["notify"] = notify_result
            logger.info(f"[Orchestrator] Sent {notify_result['total_notifications']} notifications")

            logger.info("=" * 80)
            logger.info("[Orchestrator] Pipeline execution complete!")
            logger.info(f"  Scanned:    {scan_result.get('saved_events', 0)} events")
            logger.info(f"  Extracted:  {extract_result.get('saved', 0)} events")
            logger.info(f"  Scored:     {score_result.get('scored', 0)} events")
            logger.info(f"  Matched:    {total_matches} event-user pairs")
            logger.info(f"  Notified:   {notify_result['total_notifications']} users")
            logger.info("=" * 80)

        except Exception as exc:
            logger.error(f"[Orchestrator] Pipeline failed: {exc}")
            pipeline_result["status"] = "failed"
            pipeline_result["errors"].append(str(exc))

        return pipeline_result

    async def run_pipeline_async(self) -> dict:
        return self.run_full_pipeline()

    def schedule_periodic_scan(self, interval_minutes: int = 30) -> None:
        import schedule

        logger.info(f"[Orchestrator] Scheduling periodic scan every {interval_minutes} minutes")

        def job():
            try:
                self.run_full_pipeline()
            except Exception as exc:
                logger.error(f"[Orchestrator] Scheduled job failed: {exc}")

        schedule.every(interval_minutes).minutes.do(job)
        while True:
            schedule.run_pending()
            time.sleep(1)

    def schedule_periodic_scan_background(self, interval_minutes: int = 30) -> None:
        import threading

        def run_scheduler():
            self.schedule_periodic_scan(interval_minutes)

        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()
        logger.info("[Orchestrator] Background scheduler thread started")

    def get_scan_status(self) -> dict:
        try:
            response = self.db.table("scan_jobs").select("*").order("started_at", desc=True).limit(1).execute()
            if response.data:
                status = response.data[0]
                if "source_summary" not in status and status.get("lanes"):
                    status["source_summary"] = status.get("lanes") or {}
                return status
            status = self.scanner.get_last_run_summary()
            if "source_summary" not in status and status.get("lanes"):
                status["source_summary"] = status.get("lanes") or {}
            return status
        except Exception as exc:
            logger.error(f"[Orchestrator] Failed to get scan status: {exc}")
            status = self.scanner.get_last_run_summary()
            if "source_summary" not in status and status.get("lanes"):
                status["source_summary"] = status.get("lanes") or {}
            return status

    def get_pipeline_statistics(self, days: int = 7) -> dict:
        try:
            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            scan_jobs_response = self.db.table("scan_jobs").select("*").gte("created_at", start_date).execute()
            scan_jobs = scan_jobs_response.data or []
            total_scans = len(scan_jobs)
            successful_scans = len([row for row in scan_jobs if str(row.get("status") or "").startswith("completed")])
            last_sync_time = None
            lane_statistics = {
                "news": {"runs": 0, "events_found": 0, "events_saved": 0, "blocked_runs": 0},
                "reports": {"runs": 0, "events_found": 0, "events_saved": 0, "blocked_runs": 0},
                "compliance": {"runs": 0, "events_found": 0, "events_saved": 0, "blocked_runs": 0},
            }
            for row in scan_jobs:
                completed_at = row.get("completed_at") or row.get("started_at")
                if completed_at and (last_sync_time is None or str(completed_at) > str(last_sync_time)):
                    last_sync_time = completed_at
                source_summary = row.get("source_summary") or {}
                if isinstance(source_summary, dict):
                    for lane, lane_payload in source_summary.items():
                        lane_stats = lane_statistics.get(lane)
                        if lane_stats is None:
                            continue
                        lane_stats["runs"] += 1
                        lane_stats["events_found"] += int(lane_payload.get("events_found") or 0)
                        lane_stats["events_saved"] += int(lane_payload.get("events_saved") or 0)
                        if lane_payload.get("status") in {"blocked", "degraded"}:
                            lane_stats["blocked_runs"] += 1

            scan_response = self.db.table("esg_events").select("*").gte("created_at", start_date).execute()
            total_scanned = len(scan_response.data)
            extract_response = self.db.table("extracted_events").select("*").gte("created_at", start_date).execute()
            total_extracted = len(extract_response.data)
            score_response = self.db.table("risk_scores").select("*").gte("created_at", start_date).execute()
            total_scored = len(score_response.data)
            notif_response = self.db.table("notification_logs").select("*").gte("sent_at", start_date).execute()
            total_notified = len(notif_response.data)

            return {
                "period_days": days,
                "total_scans": total_scans,
                "last_sync_time": last_sync_time,
                "lane_statistics": lane_statistics,
                "total_scanned": total_scanned,
                "total_extracted": total_extracted,
                "total_scored": total_scored,
                "total_notified": total_notified,
                "success_rate": round((successful_scans / total_scans) * 100, 2) if total_scans > 0 else 0,
            }
        except Exception as exc:
            logger.error(f"[Orchestrator] Failed to get statistics: {exc}")
            return {}


_orchestrator = None


def get_orchestrator() -> SchedulerOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SchedulerOrchestrator()
    return _orchestrator
