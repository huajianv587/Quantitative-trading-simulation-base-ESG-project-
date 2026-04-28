from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import schedule
from pydantic import BaseModel

from gateway.db.supabase_client import supabase_client
from gateway.scheduler.data_sources import DataSourceManager
from gateway.scheduler.notifier import Notifier
from gateway.scheduler.report_generator import ESGReport, ESGReportGenerator
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class PushRule(BaseModel):
    id: Optional[str] = None
    rule_name: str
    condition: str
    target_users: str
    push_channels: List[str]
    priority: int
    template_id: str
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportSubscription(BaseModel):
    user_id: str
    report_types: List[str]
    companies: List[str]
    alert_threshold: Dict[str, Any]
    push_channels: List[str]
    frequency: str


class ReportScheduler:
    """Generate persisted ESG reports and push them using real user/report context."""

    def __init__(self):
        self.report_generator = ESGReportGenerator()
        self.data_source_manager = DataSourceManager()
        self.notifier = Notifier()
        self.scheduler_thread = None
        self.is_running = False
        self.push_rules_cache: dict[str, PushRule] = {}
        self._load_push_rules()

    def start_background_scheduler(self):
        if self.is_running:
            logger.warning("[ReportScheduler] Scheduler already running")
            return
        logger.info("[ReportScheduler] Starting background scheduler")
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def stop_background_scheduler(self):
        self.is_running = False
        logger.info("[ReportScheduler] Scheduler stopped")

    def _run_scheduler(self):
        schedule.every().day.at("06:00").do(self.generate_and_push_daily_report)
        schedule.every().monday.at("08:00").do(self.generate_and_push_weekly_report)
        schedule.every().day.at("09:00").do(self.check_monthly_and_generate)

        logger.info("[ReportScheduler] Scheduler started with daily/weekly/monthly jobs")
        while self.is_running:
            try:
                schedule.run_pending()
                if not self.is_running:
                    break
            except Exception as exc:
                logger.error(f"[ReportScheduler] Scheduler loop error: {exc}")
            threading.Event().wait(10)

    def generate_and_push_daily_report(self):
        logger.info("[ReportScheduler] Generating daily report")
        try:
            companies = self._get_all_tracked_companies()
            if not companies:
                blocked = self._build_blocked_result(
                    report_type="daily",
                    reason="tracked_companies_missing",
                    next_actions=["Add followed companies or sync holdings before generating the daily report."],
                )
                logger.warning(f"[ReportScheduler] Daily report blocked: {blocked}")
                return blocked

            report = self.report_generator.generate_daily_report(companies)
            report_id = self._save_report(report)
            self.intelligent_push(report_id, report, "daily")
            logger.info("[ReportScheduler] Daily report completed")
            return {"status": "completed", "report_id": report_id, "companies": companies}
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error generating daily report: {exc}")
            return {"status": "failed", "error": str(exc)}

    def generate_and_push_weekly_report(self):
        logger.info("[ReportScheduler] Generating weekly report")
        try:
            companies = self._get_all_tracked_companies()
            if not companies:
                blocked = self._build_blocked_result(
                    report_type="weekly",
                    reason="tracked_companies_missing",
                    next_actions=["Add followed companies or sync holdings before generating the weekly report."],
                )
                logger.warning(f"[ReportScheduler] Weekly report blocked: {blocked}")
                return blocked

            report = self.report_generator.generate_weekly_report(companies)
            report_id = self._save_report(report)
            self.intelligent_push(report_id, report, "weekly")
            logger.info("[ReportScheduler] Weekly report completed")
            return {"status": "completed", "report_id": report_id, "companies": companies}
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error generating weekly report: {exc}")
            return {"status": "failed", "error": str(exc)}

    def check_monthly_and_generate(self):
        if datetime.now().day == 1:
            return self.generate_monthly_report()
        return {"status": "skipped", "reason": "not_first_day"}

    def generate_monthly_report(self):
        logger.info("[ReportScheduler] Generating monthly report")
        try:
            portfolio = self._get_portfolio_companies()
            if not portfolio:
                blocked = self._build_blocked_result(
                    report_type="monthly",
                    reason="portfolio_holdings_missing",
                    next_actions=["Sync real portfolio holdings before generating the monthly report."],
                )
                logger.warning(f"[ReportScheduler] Monthly report blocked: {blocked}")
                return blocked

            report = self.report_generator.generate_monthly_report(portfolio)
            report_id = self._save_report(report)
            self.intelligent_push(report_id, report, "monthly")
            logger.info("[ReportScheduler] Monthly report completed")
            return {"status": "completed", "report_id": report_id, "companies": portfolio}
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error generating monthly report: {exc}")
            return {"status": "failed", "error": str(exc)}

    def intelligent_push(self, report_id: str, report: ESGReport, report_type: str):
        logger.info(f"[ReportScheduler] Starting intelligent push for report {report_id}")
        try:
            matched_rules = self._match_push_rules(report, report_type)
            for rule in matched_rules:
                users = self._get_target_users(rule, report)
                for user_id in users:
                    self.notifier.send_notification(
                        user_id=user_id,
                        report_id=report_id,
                        title=report.title,
                        content=self._generate_notification_content(report, user_id),
                        severity=self._get_push_severity(report),
                        channels=rule.push_channels,
                        template_id=rule.template_id,
                    )
            logger.info(f"[ReportScheduler] Push completed for report {report_id}")
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error during intelligent push: {exc}")

    def _match_push_rules(self, report: ESGReport, report_type: str) -> List[PushRule]:
        matched: list[PushRule] = []
        for rule in self.push_rules_cache.values():
            if not rule.enabled:
                continue
            try:
                context = {
                    "report_type": report_type,
                    "overall_score": report.report_statistics.get("portfolio_average_score", 0),
                    "company_count": len(report.company_analyses),
                    "risk_alert_count": len(report.risk_alerts),
                    "high_performer_count": len([item for item in report.company_analyses if item.esg_score >= 80]),
                    "low_performer_count": len([item for item in report.company_analyses if item.esg_score < 40]),
                }
                if eval(rule.condition, {"__builtins__": {}}, context):
                    matched.append(rule)
            except Exception as exc:
                logger.warning(f"[ReportScheduler] Error evaluating rule {rule.rule_name}: {exc}")
        return sorted(matched, key=lambda item: item.priority, reverse=True)

    def _get_target_users(self, rule: PushRule, report: ESGReport) -> List[str]:
        companies = [analysis.company_name for analysis in report.company_analyses]
        if rule.target_users == "all":
            return self._get_all_users()
        if rule.target_users == "holders":
            return self._get_users_with_holdings(companies)
        if rule.target_users == "followers":
            return self._get_users_following_companies(companies)
        if rule.target_users == "analysts":
            return self._get_industry_analysts(report)
        return []

    def _save_report(self, report: ESGReport) -> str:
        report_id = str(uuid.uuid4())
        report_payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report.dict()
        period_start = report.period_start.isoformat()
        period_end = report.period_end.isoformat()
        persisted_payload = {
            "report_type": report.report_type,
            "title": report.title,
            "period_start": period_start,
            "period_end": period_end,
            "data": report_payload,
            "generated_at": datetime.now().isoformat(),
        }

        try:
            supabase_client.table("esg_reports").insert({"id": report_id, **persisted_payload}).execute()
            logger.info(f"[ReportScheduler] Report {report_id} saved to database")
            return report_id
        except Exception as exc:
            error_text = str(exc).lower()
            if "duplicate key" in error_text or "unique constraint" in error_text:
                existing_id = self._reuse_duplicate_report(report, persisted_payload, period_start, period_end)
                if existing_id:
                    return existing_id
            logger.error(f"[ReportScheduler] Error saving report: {exc}")
            raise

    def _reuse_duplicate_report(
        self,
        report: ESGReport,
        persisted_payload: dict[str, Any],
        period_start: str,
        period_end: str,
    ) -> str | None:
        try:
            rows = (
                supabase_client.table("esg_reports")
                .select("id")
                .eq("report_type", report.report_type)
                .eq("period_start", period_start)
                .eq("period_end", period_end)
                .limit(1)
                .execute()
                .data
            )
            if not rows:
                return None
            existing_id = str(rows[0]["id"])
            try:
                supabase_client.table("esg_reports").update(persisted_payload).eq("id", existing_id).execute()
            except Exception as update_exc:
                logger.warning(f"[ReportScheduler] Duplicate report update skipped: {update_exc}")
            logger.info(f"[ReportScheduler] Reused existing report {existing_id} for identical period payload")
            return existing_id
        except Exception as lookup_exc:
            logger.warning(f"[ReportScheduler] Duplicate report lookup failed: {lookup_exc}")
            return None

    def _load_push_rules(self):
        try:
            rows = supabase_client.table("push_rules").select("*").eq("enabled", True).execute().data
            self.push_rules_cache = {str(PushRule(**row).id): PushRule(**row) for row in rows}
            logger.info(f"[ReportScheduler] Loaded {len(self.push_rules_cache)} push rules")
        except Exception as exc:
            logger.warning(f"[ReportScheduler] Error loading push rules: {exc}")

    def create_push_rule(self, rule: PushRule) -> str:
        rule.id = str(uuid.uuid4())
        rule.created_at = datetime.now()
        rule.updated_at = datetime.now()
        payload = rule.model_dump(mode="json") if hasattr(rule, "model_dump") else rule.dict()
        try:
            supabase_client.table("push_rules").insert(payload).execute()
            self.push_rules_cache[str(rule.id)] = rule
            logger.info(f"[ReportScheduler] Push rule {rule.id} created")
            return str(rule.id)
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error creating push rule: {exc}")
            raise

    def update_push_rule(self, rule_id: str, updates: Dict[str, Any]):
        try:
            supabase_client.table("push_rules").update(updates).eq("id", rule_id).execute()
            if rule_id in self.push_rules_cache:
                rule = self.push_rules_cache[rule_id]
                for key, value in updates.items():
                    setattr(rule, key, value)
            logger.info(f"[ReportScheduler] Push rule {rule_id} updated")
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error updating push rule: {exc}")
            raise

    def delete_push_rule(self, rule_id: str):
        try:
            supabase_client.table("push_rules").delete().eq("id", rule_id).execute()
            self.push_rules_cache.pop(rule_id, None)
            logger.info(f"[ReportScheduler] Push rule {rule_id} deleted")
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error deleting push rule: {exc}")
            raise

    def user_subscribe_reports(self, subscription: ReportSubscription):
        try:
            response = supabase_client.table("user_report_subscriptions").insert(
                {
                    "user_id": subscription.user_id,
                    "report_types": subscription.report_types,
                    "companies": subscription.companies,
                    "alert_threshold": subscription.alert_threshold,
                    "push_channels": subscription.push_channels,
                    "frequency": subscription.frequency,
                    "subscribed_at": datetime.now().isoformat(),
                }
            ).execute()
            logger.info(f"[ReportScheduler] User {subscription.user_id} subscribed to reports")
            if response.data:
                return response.data[0].get("id")
            return None
        except Exception as exc:
            logger.error(f"[ReportScheduler] Error subscribing user: {exc}")
            raise

    def _get_preference_companies(self) -> List[str]:
        try:
            prefs = supabase_client.table("user_preferences").select("interested_companies").execute().data
            companies = set()
            for pref in prefs:
                companies.update(str(item).strip() for item in (pref.get("interested_companies") or []) if str(item).strip())
            return sorted(companies)
        except Exception as exc:
            logger.warning(f"[ReportScheduler] Error getting preference companies: {exc}")
            return []

    def _get_all_tracked_companies(self) -> List[str]:
        companies = set()
        companies.update(self._get_preference_companies())
        companies.update(self._get_portfolio_companies())
        return sorted(company for company in companies if company)

    def _get_portfolio_companies(self) -> List[str]:
        try:
            rows = supabase_client.table("user_holdings").select("company_name,company").execute().data
            companies = set()
            for row in rows:
                if row.get("company_name"):
                    companies.add(str(row["company_name"]).strip())
                elif row.get("company"):
                    companies.add(str(row["company"]).strip())
            return sorted(company for company in companies if company)
        except Exception as exc:
            logger.warning(f"[ReportScheduler] Error getting portfolio companies: {exc}")
            return []

    def _get_all_users(self) -> List[str]:
        try:
            rows = supabase_client.table("users").select("user_id").execute().data
            return [str(row["user_id"]) for row in rows if row.get("user_id")]
        except Exception:
            return []

    def _get_users_with_holdings(self, companies: List[str]) -> List[str]:
        try:
            company_keys = {str(company).strip().lower() for company in companies if str(company).strip()}
            rows = supabase_client.table("user_holdings").select("user_id,company_name,company").execute().data
            users = set()
            for row in rows:
                company_name = str(row.get("company_name") or row.get("company") or "").strip().lower()
                if company_name and company_name in company_keys and row.get("user_id"):
                    users.add(str(row["user_id"]))
            return sorted(users)
        except Exception:
            return []

    def _get_users_following_companies(self, companies: List[str]) -> List[str]:
        try:
            company_keys = {str(company).strip().lower() for company in companies if str(company).strip()}
            prefs = supabase_client.table("user_preferences").select("user_id,interested_companies").execute().data
            users = set()
            for pref in prefs:
                followed = {str(item).strip().lower() for item in (pref.get("interested_companies") or []) if str(item).strip()}
                if followed & company_keys and pref.get("user_id"):
                    users.add(str(pref["user_id"]))
            return sorted(users)
        except Exception:
            return []

    def _get_industry_analysts(self, report: ESGReport) -> List[str]:
        try:
            analysts = supabase_client.table("users").select("user_id").eq("role", "analyst").execute().data
            return [str(row["user_id"]) for row in analysts if row.get("user_id")]
        except Exception:
            return []

    def _generate_notification_content(self, report: ESGReport, user_id: str) -> str:
        if report.report_type == "daily":
            return f"Daily ESG update: {len(report.company_analyses)} tracked companies, {len(report.risk_alerts)} risk alerts."
        if report.report_type == "weekly":
            avg = report.report_statistics.get("average_score", 0)
            return f"Weekly ESG update: tracked-company average score is {avg:.1f}/100."
        portfolio_avg = report.report_statistics.get("portfolio_average_score", 0)
        return f"Portfolio ESG update: average score is {portfolio_avg:.1f}/100."

    def _get_push_severity(self, report: ESGReport) -> str:
        if report.report_statistics.get("portfolio_average_score", 0) < 40:
            return "critical"
        if len(report.risk_alerts) > 5:
            return "high"
        return "medium"

    @staticmethod
    def _build_blocked_result(report_type: str, reason: str, next_actions: List[str]) -> Dict[str, Any]:
        return {
            "status": "blocked",
            "report_type": report_type,
            "block_reason": reason,
            "next_actions": [action for action in next_actions if str(action).strip()],
        }
