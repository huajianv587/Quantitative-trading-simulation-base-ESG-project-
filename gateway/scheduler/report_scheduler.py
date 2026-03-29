# report_scheduler.py — ESG 报告自动化调度和推送
# 职责：定期生成报告，并根据规则智能推送给用户

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import schedule
import threading
from gateway.utils.logger import get_logger
from gateway.scheduler.report_generator import ESGReportGenerator, ESGReport
from gateway.scheduler.data_sources import DataSourceManager
from gateway.scheduler.notifier import Notifier
from gateway.db.supabase_client import supabase_client

logger = get_logger(__name__)


# ── 推送规则数据模型 ──────────────────────────────────────────────────────

class PushRule(BaseModel):
    """推送规则"""
    id: Optional[str] = None
    rule_name: str
    condition: str  # Python表达式，如 "esg_score < 40 and change < -5"
    target_users: str  # "all", "holders", "followers", "analysts"
    push_channels: List[str]  # ["in_app", "email", "webhook"]
    priority: int  # 1-10，值越大优先级越高
    template_id: str
    enabled: bool = True
    created_at: datetime = None
    updated_at: datetime = None


class ReportSubscription(BaseModel):
    """用户的报告订阅"""
    user_id: str
    report_types: List[str]  # ["daily", "weekly", "monthly"]
    companies: List[str]  # 关注的公司
    alert_threshold: Dict[str, Any]  # {"esg_score": 40, "change": -5}
    push_channels: List[str]
    frequency: str  # "immediate", "daily", "weekly"


# ── 报告调度器 ─────────────────────────────────────────────────────────────

class ReportScheduler:
    """
    自动化报告调度和推送引擎
    负责：
    1. 定期生成日/周/月报告
    2. 存储到数据库
    3. 根据推送规则智能推送
    4. 跟踪推送效果
    """

    def __init__(self):
        """初始化报告调度器"""
        self.report_generator = ESGReportGenerator()
        self.data_source_manager = DataSourceManager()
        self.notifier = Notifier()

        self.scheduler_thread = None
        self.is_running = False

        # 推送规则缓存
        self.push_rules_cache = {}
        self._load_push_rules()

    def start_background_scheduler(self):
        """启动后台调度线程"""
        if self.is_running:
            logger.warning("[ReportScheduler] Scheduler already running")
            return

        logger.info("[ReportScheduler] Starting background scheduler")

        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def stop_background_scheduler(self):
        """停止后台调度线程"""
        self.is_running = False
        logger.info("[ReportScheduler] Scheduler stopped")

    def _run_scheduler(self):
        """运行调度循环"""
        # 设置定期任务
        schedule.every().day.at("06:00").do(self.generate_and_push_daily_report)
        schedule.every().monday.at("08:00").do(self.generate_and_push_weekly_report)
        schedule.every().day.at("09:00").do(self.check_monthly_and_generate)

        logger.info("[ReportScheduler] Scheduler started with tasks:")
        logger.info("  - Daily report: 06:00 UTC")
        logger.info("  - Weekly report: Every Monday 08:00 UTC")
        logger.info("  - Monthly report: 1st day of month 09:00 UTC")

        # 运行调度循环
        while self.is_running:
            try:
                schedule.run_pending()
                # 检查是否需要停止
                if not self.is_running:
                    break
            except Exception as e:
                logger.error(f"[ReportScheduler] Scheduler error: {e}")

            # 每10秒检查一次
            threading.Event().wait(10)

    def generate_and_push_daily_report(self):
        """生成并推送日报"""
        logger.info("[ReportScheduler] Generating daily report")

        try:
            # 获取所有用户关注的公司列表
            companies = self._get_all_tracked_companies()

            # 生成日报
            report = self.report_generator.generate_daily_report(companies)

            # 保存到数据库
            report_id = self._save_report(report)

            # 智能推送
            self.intelligent_push(report_id, report, "daily")

            logger.info("[ReportScheduler] Daily report completed")

        except Exception as e:
            logger.error(f"[ReportScheduler] Error generating daily report: {e}")

    def generate_and_push_weekly_report(self):
        """生成并推送周报"""
        logger.info("[ReportScheduler] Generating weekly report")

        try:
            companies = self._get_all_tracked_companies()
            report = self.report_generator.generate_weekly_report(companies)
            report_id = self._save_report(report)
            self.intelligent_push(report_id, report, "weekly")

            logger.info("[ReportScheduler] Weekly report completed")

        except Exception as e:
            logger.error(f"[ReportScheduler] Error generating weekly report: {e}")

    def check_monthly_and_generate(self):
        """检查是否是月初，如果是则生成月报"""
        if datetime.now().day == 1:
            self.generate_monthly_report()

    def generate_monthly_report(self):
        """生成并推送月报"""
        logger.info("[ReportScheduler] Generating monthly report")

        try:
            portfolio = self._get_portfolio_companies()
            report = self.report_generator.generate_monthly_report(portfolio)
            report_id = self._save_report(report)
            self.intelligent_push(report_id, report, "monthly")

            logger.info("[ReportScheduler] Monthly report completed")

        except Exception as e:
            logger.error(f"[ReportScheduler] Error generating monthly report: {e}")

    def intelligent_push(self, report_id: str, report: ESGReport, report_type: str):
        """
        智能推送报告给用户
        根据推送规则和用户偏好进行过滤和个性化推送

        推送策略：
        - 优秀报告（综合评分>80）：推送给所有用户
        - 低分预警（综合评分<40）：推送给持有人
        - 风险突变（评分变化>-5）：推送给关注者
        - 行业热点：推送给行业分析师
        """
        logger.info(f"[ReportScheduler] Starting intelligent push for report {report_id}")

        try:
            # 遍历所有推送规则
            matched_rules = self._match_push_rules(report, report_type)

            for rule in matched_rules:
                # 获取规则对应的用户列表
                users = self._get_target_users(rule, report)

                # 为每个用户生成个性化内容并推送
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

        except Exception as e:
            logger.error(f"[ReportScheduler] Error during intelligent push: {e}")

    def _match_push_rules(self, report: ESGReport, report_type: str) -> List[PushRule]:
        """
        匹配适用的推送规则
        """
        matched = []

        for rule_id, rule in self.push_rules_cache.items():
            if not rule.enabled:
                continue

            try:
                # 构建用于规则评估的上下文
                context = {
                    "report_type": report_type,
                    "overall_score": report.report_statistics.get("portfolio_average_score", 0),
                    "company_count": len(report.company_analyses),
                    "risk_alert_count": len(report.risk_alerts),
                    "high_performer_count": len([a for a in report.company_analyses if a.esg_score >= 80]),
                    "low_performer_count": len([a for a in report.company_analyses if a.esg_score < 40]),
                }

                # 评估规则条件
                if eval(rule.condition, {"__builtins__": {}}, context):
                    matched.append(rule)

            except Exception as e:
                logger.warning(f"[ReportScheduler] Error evaluating rule {rule.rule_name}: {e}")

        return sorted(matched, key=lambda r: r.priority, reverse=True)

    def _get_target_users(self, rule: PushRule, report: ESGReport) -> List[str]:
        """根据推送规则获取目标用户"""
        if rule.target_users == "all":
            return self._get_all_users()

        elif rule.target_users == "holders":
            # 获取持有相关公司股票的用户
            companies = [a.company_name for a in report.company_analyses]
            return self._get_users_with_holdings(companies)

        elif rule.target_users == "followers":
            # 获取关注相关公司的用户
            companies = [a.company_name for a in report.company_analyses]
            return self._get_users_following_companies(companies)

        elif rule.target_users == "analysts":
            # 获取行业分析师
            return self._get_industry_analysts(report)

        return []

    def _save_report(self, report: ESGReport) -> str:
        """将报告保存到数据库"""
        report_id = str(uuid.uuid4())

        try:
            supabase_client.table("esg_reports").insert({
                "id": report_id,
                "report_type": report.report_type,
                "title": report.title,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "data": report.dict(),
                "generated_at": datetime.now().isoformat(),
            }).execute()

            logger.info(f"[ReportScheduler] Report {report_id} saved to database")
            return report_id

        except Exception as e:
            logger.error(f"[ReportScheduler] Error saving report: {e}")
            return report_id

    def _load_push_rules(self):
        """从数据库加载推送规则"""
        try:
            rules = supabase_client.table("push_rules").select("*").eq("enabled", True).execute().data

            self.push_rules_cache = {}
            for rule_data in rules:
                rule = PushRule(**rule_data)
                self.push_rules_cache[rule.id] = rule

            logger.info(f"[ReportScheduler] Loaded {len(self.push_rules_cache)} push rules")

        except Exception as e:
            logger.warning(f"[ReportScheduler] Error loading push rules: {e}")

    def create_push_rule(self, rule: PushRule) -> str:
        """创建新的推送规则"""
        rule.id = str(uuid.uuid4())
        rule.created_at = datetime.now()
        rule.updated_at = datetime.now()

        try:
            supabase_client.table("push_rules").insert(rule.dict()).execute()
            self.push_rules_cache[rule.id] = rule

            logger.info(f"[ReportScheduler] Push rule {rule.id} created: {rule.rule_name}")
            return rule.id

        except Exception as e:
            logger.error(f"[ReportScheduler] Error creating push rule: {e}")
            raise

    def update_push_rule(self, rule_id: str, updates: Dict[str, Any]):
        """更新推送规则"""
        try:
            supabase_client.table("push_rules").update(updates).eq("id", rule_id).execute()

            # 更新缓存
            if rule_id in self.push_rules_cache:
                rule = self.push_rules_cache[rule_id]
                for key, value in updates.items():
                    setattr(rule, key, value)

            logger.info(f"[ReportScheduler] Push rule {rule_id} updated")

        except Exception as e:
            logger.error(f"[ReportScheduler] Error updating push rule: {e}")

    def delete_push_rule(self, rule_id: str):
        """删除推送规则"""
        try:
            supabase_client.table("push_rules").delete().eq("id", rule_id).execute()

            if rule_id in self.push_rules_cache:
                del self.push_rules_cache[rule_id]

            logger.info(f"[ReportScheduler] Push rule {rule_id} deleted")

        except Exception as e:
            logger.error(f"[ReportScheduler] Error deleting push rule: {e}")

    def user_subscribe_reports(self, subscription: ReportSubscription):
        """用户订阅报告"""
        try:
            supabase_client.table("user_report_subscriptions").insert({
                "user_id": subscription.user_id,
                "report_types": subscription.report_types,
                "companies": subscription.companies,
                "alert_threshold": subscription.alert_threshold,
                "push_channels": subscription.push_channels,
                "frequency": subscription.frequency,
                "subscribed_at": datetime.now().isoformat(),
            }).execute()

            logger.info(f"[ReportScheduler] User {subscription.user_id} subscribed to reports")

        except Exception as e:
            logger.error(f"[ReportScheduler] Error subscribing user: {e}")

    # ── 辅助方法 ──────────────────────────────────────────────────────────

    def _get_all_tracked_companies(self) -> List[str]:
        """获取所有被追踪的公司"""
        try:
            prefs = supabase_client.table("user_preferences").select("interested_companies").execute().data
            companies = set()
            for pref in prefs:
                companies.update(pref.get("interested_companies", []))
            return list(companies)
        except Exception as e:
            logger.warning(f"[ReportScheduler] Error getting tracked companies: {e}")
            return []

    def _get_portfolio_companies(self) -> List[str]:
        """获取投资组合中的所有公司"""
        # 这通常需要从用户的持仓数据中获取
        # 这里用示例实现
        return self._get_all_tracked_companies()

    def _get_all_users(self) -> List[str]:
        """获取所有用户"""
        try:
            users = supabase_client.table("users").select("id").execute().data
            return [u["id"] for u in users]
        except Exception:
            return []

    def _get_users_with_holdings(self, companies: List[str]) -> List[str]:
        """获取持有特定公司的用户"""
        try:
            # 这需要一个持仓表或关联表
            users = supabase_client.table("user_holdings").select("user_id").in_("company", companies).execute().data
            return list(set([u["user_id"] for u in users]))
        except Exception:
            return []

    def _get_users_following_companies(self, companies: List[str]) -> List[str]:
        """获取关注特定公司的用户"""
        try:
            prefs = supabase_client.table("user_preferences").select("user_id,interested_companies").execute().data
            users = []
            for pref in prefs:
                if any(c in pref.get("interested_companies", []) for c in companies):
                    users.append(pref["user_id"])
            return users
        except Exception:
            return []

    def _get_industry_analysts(self, report: ESGReport) -> List[str]:
        """获取行业分析师"""
        # 需要一个用户角色/权限表来识别分析师
        try:
            analysts = supabase_client.table("users").select("id").eq("role", "analyst").execute().data
            return [a["id"] for a in analysts]
        except Exception:
            return []

    def _generate_notification_content(self, report: ESGReport, user_id: str) -> str:
        """生成个性化的通知内容"""
        # 这里可以根据用户偏好生成不同的内容
        if report.report_type == "daily":
            return f"您关注的企业今日有 {len(report.company_analyses)} 条ESG新闻，其中{len(report.risk_alerts)}条高风险预警。"
        elif report.report_type == "weekly":
            avg = report.report_statistics.get("average_score", 0)
            return f"本周监控的企业ESG平均评分为 {avg:.1f}/100。"
        else:
            portfolio_avg = report.report_statistics.get("portfolio_average_score", 0)
            return f"您的投资组合ESG评分为 {portfolio_avg:.1f}/100。"

    def _get_push_severity(self, report: ESGReport) -> str:
        """根据报告内容判断推送级别"""
        if report.report_statistics.get("portfolio_average_score", 0) < 40:
            return "critical"
        elif len(report.risk_alerts) > 5:
            return "high"
        else:
            return "medium"
