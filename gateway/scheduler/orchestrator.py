# orchestrator.py — 调度器编排器
# 职责：协调 scanner → extractor → matcher → risk_scorer → notifier 整个流程
# 这是主动扫描和推送的大脑

import asyncio
from datetime import datetime, timezone
from typing import Optional

from gateway.utils.logger import get_logger
from gateway.scheduler.scanner import get_scanner
from gateway.scheduler.event_extractor import get_extractor
from gateway.scheduler.matcher import get_matcher
from gateway.scheduler.risk_scorer import get_risk_scorer
from gateway.scheduler.notifier import get_notifier
from gateway.db.supabase_client import get_client
from gateway.rag.event_indexer import index_events_async

logger = get_logger(__name__)


class SchedulerOrchestrator:
    """调度器编排器 - 协调整个主动扫描→分析→推送流程"""

    def __init__(self):
        self.scanner = get_scanner()
        self.extractor = get_extractor()
        self.matcher = get_matcher()
        self.risk_scorer = get_risk_scorer()
        self.notifier = get_notifier()
        self.db = get_client()

    def run_full_pipeline(self) -> dict:
        """
        执行完整的扫描→分析→推送流程。

        流程：
        1. Scanner: 扫描新的 ESG 事件
        2. Extractor: 提取结构化信息
        3. RiskScorer: 评分风险
        4. Matcher: 匹配相关用户
        5. Notifier: 推送通知

        Returns:
            完整流程执行结果
        """
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
            # ── Stage 1: Scanner ─────────────────────────────────────────────
            logger.info("[Orchestrator] Stage 1/5: Scanning for new events...")
            scan_result = self.scanner.run_scan()
            pipeline_result["stages"]["scan"] = scan_result

            if not scan_result.get("saved_events", 0):
                logger.info("[Orchestrator] No new events found, exiting pipeline.")
                return pipeline_result

            event_ids = scan_result.get("event_ids", [])
            logger.info(f"[Orchestrator] Found {len(event_ids)} new events")

            # ── Stage 2: Extractor ──────────────────────────────────────────
            logger.info("[Orchestrator] Stage 2/5: Extracting structured information...")
            extract_result = self.extractor.process_new_events(event_ids)
            pipeline_result["stages"]["extract"] = extract_result

            if not extract_result.get("saved", 0):
                logger.warning("[Orchestrator] No events extracted successfully")
                pipeline_result["status"] = "partial"

            extracted_ids = extract_result.get("saved_ids", [])
            logger.info(f"[Orchestrator] Extracted {len(extracted_ids)} events")

            # ── Stage 2.5: RAG Indexing (async) ────────────────────────────
            # 异步写入 Qdrant，不阻塞后续 RiskScorer/Matcher/Notifier 流程
            # Supabase 已在 Stage 2 写入，这里并行写向量库
            if extracted_ids:
                index_events_async(extracted_ids)

            # ── Stage 3: RiskScorer ─────────────────────────────────────────
            logger.info("[Orchestrator] Stage 3/5: Scoring risk levels...")
            score_result = self.risk_scorer.score_batch_events(extracted_ids)
            pipeline_result["stages"]["risk_score"] = score_result

            logger.info(f"[Orchestrator] Scored {score_result.get('scored', 0)} events")

            # ── Stage 4: Matcher ─────────────────────────────────────────────
            logger.info("[Orchestrator] Stage 4/5: Matching events to users...")
            match_result = self.matcher.match_batch_events(extracted_ids)
            pipeline_result["stages"]["match"] = match_result

            total_matches = match_result.get("total_matches", 0)
            logger.info(f"[Orchestrator] Matched {total_matches} event-user pairs")

            # ── Stage 5: Notifier ────────────────────────────────────────────
            logger.info("[Orchestrator] Stage 5/5: Sending notifications...")
            notify_result = {
                "total_events": len(extracted_ids),
                "total_notifications": 0,
                "by_event": [],
            }

            for event_id in extracted_ids:
                # 从 match_result 中找出该事件的匹配用户
                event_matches = next(
                    (r for r in match_result.get("results", []) if r.get("event_id") == event_id),
                    None,
                )

                if event_matches:
                    matched_users = event_matches.get("matched_users", [])
                    if matched_users:
                        notification_result = self.notifier.send_notifications(event_id, matched_users)
                        notify_result["by_event"].append({
                            "event_id": event_id,
                            **notification_result,
                        })
                        notify_result["total_notifications"] += notification_result.get("sent", 0)

            pipeline_result["stages"]["notify"] = notify_result
            logger.info(f"[Orchestrator] Sent {notify_result['total_notifications']} notifications")

            # ── Summary ──────────────────────────────────────────────────────
            logger.info("=" * 80)
            logger.info("[Orchestrator] Pipeline execution complete!")
            logger.info(f"  Scanned:    {scan_result.get('saved_events', 0)} events")
            logger.info(f"  Extracted:  {extract_result.get('saved', 0)} events")
            logger.info(f"  Scored:     {score_result.get('scored', 0)} events")
            logger.info(f"  Matched:    {total_matches} event-user pairs")
            logger.info(f"  Notified:   {notify_result['total_notifications']} users")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"[Orchestrator] Pipeline failed: {e}")
            pipeline_result["status"] = "failed"
            pipeline_result["errors"].append(str(e))

        return pipeline_result

    async def run_pipeline_async(self) -> dict:
        """
        异步执行流程（可用于并行化某些步骤）。

        当前仍然是顺序执行，但架构支持后续改进为并行。
        """
        # TODO: 实现并行执行（如 scanner 和 extractor 并行）
        return self.run_full_pipeline()

    def schedule_periodic_scan(self, interval_minutes: int = 30) -> None:
        """
        定期执行扫描流程。

        Args:
            interval_minutes: 扫描间隔（分钟）
        """
        import schedule
        import time

        logger.info(f"[Orchestrator] Scheduling periodic scan every {interval_minutes} minutes")

        def job():
            try:
                self.run_full_pipeline()
            except Exception as e:
                logger.error(f"[Orchestrator] Scheduled job failed: {e}")

        # 每隔 interval_minutes 执行一次
        schedule.every(interval_minutes).minutes.do(job)

        # 保持调度器运行（阻塞）
        while True:
            schedule.run_pending()
            time.sleep(1)

    def schedule_periodic_scan_background(self, interval_minutes: int = 30) -> None:
        """
        后台定期执行扫描（非阻塞）。

        使用线程在后台执行，允许主程序继续运行。

        Args:
            interval_minutes: 扫描间隔（分钟）
        """
        import threading

        def run_scheduler():
            self.schedule_periodic_scan(interval_minutes)

        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()
        logger.info(f"[Orchestrator] Background scheduler thread started")

    def get_scan_status(self) -> dict:
        """获取最近一次扫描的状态"""
        try:
            response = self.db.table("scan_jobs").select("*").order("started_at", desc=True).limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to get scan status: {e}")
            return None

    def get_pipeline_statistics(self, days: int = 7) -> dict:
        """获取最近 N 天的流程统计"""
        try:
            from datetime import timedelta

            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            # 获取扫描统计
            scan_response = self.db.table("esg_events").select("*").gte("created_at", start_date).execute()
            total_scanned = len(scan_response.data)

            # 获取提取统计
            extract_response = self.db.table("extracted_events").select("*").gte("created_at", start_date).execute()
            total_extracted = len(extract_response.data)

            # 获取评分统计
            score_response = self.db.table("risk_scores").select("*").gte("created_at", start_date).execute()
            total_scored = len(score_response.data)

            # 获取推送统计
            notif_response = self.db.table("notification_logs").select("*").gte("sent_at", start_date).execute()
            total_notified = len(notif_response.data)

            return {
                "period_days": days,
                "total_scanned": total_scanned,
                "total_extracted": total_extracted,
                "total_scored": total_scored,
                "total_notified": total_notified,
                "success_rate": (total_extracted / total_scanned * 100) if total_scanned > 0 else 0,
            }

        except Exception as e:
            logger.error(f"[Orchestrator] Failed to get statistics: {e}")
            return {}


# ── 全局单例 ──────────────────────────────────────────────────────────────

_orchestrator = None

def get_orchestrator() -> SchedulerOrchestrator:
    """获取调度器编排器实例（单例）"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SchedulerOrchestrator()
    return _orchestrator
