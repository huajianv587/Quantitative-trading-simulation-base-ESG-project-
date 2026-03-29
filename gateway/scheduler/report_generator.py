# report_generator.py — ESG 报告生成引擎
# 职责：根据收集的数据和评分结果，生成日/周/月ESG报告

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from gateway.utils.llm_client import chat
from gateway.utils.logger import get_logger
from gateway.agents.esg_scorer import ESGScoringFramework, ESGScoreReport
from gateway.agents.esg_visualizer import ESGVisualizer

logger = get_logger(__name__)


# ── 报告数据模型 ──────────────────────────────────────────────────────────

class RiskAlert(BaseModel):
    """风险预警"""
    company: str
    risk_level: str  # "critical", "high", "medium"
    category: str    # "E", "S", "G"
    title: str
    description: str
    impact: str
    recommendation: str
    affected_areas: List[str]
    alert_date: datetime


class BestPractice(BaseModel):
    """最佳实践"""
    company: str
    category: str  # "E", "S", "G"
    title: str
    description: str
    impact: str
    benchmark_score: float


class CompanyAnalysis(BaseModel):
    """单个公司的分析"""
    company_name: str
    ticker: Optional[str] = None
    esg_score: float
    score_change: Optional[float] = None  # 与上期对比
    trend: str  # "up", "down", "stable"
    summary: str
    key_metrics: Dict[str, Any]
    peer_rank: Optional[str] = None


class ESGReport(BaseModel):
    """ESG 报告"""
    report_type: str  # "daily", "weekly", "monthly"
    title: str
    period_start: datetime
    period_end: datetime

    # 报告内容
    executive_summary: str
    key_findings: List[str]
    company_analyses: List[CompanyAnalysis]
    risk_alerts: List[RiskAlert]
    best_practices: List[BestPractice]

    # 统计和对标
    report_statistics: Dict[str, Any]

    # 可视化数据
    visualizations: Dict[str, Any]

    # 元数据
    generated_at: datetime
    data_sources: List[str]
    confidence_score: float


# ── 报告生成器 ─────────────────────────────────────────────────────────────

class ESGReportGenerator:
    """
    ESG 报告生成引擎
    支持日报、周报、月报三种类型
    """

    REPORT_SYSTEM_PROMPT = """你是一位资深的ESG分析顾问。
根据企业的ESG评分数据和市场信息，生成高质量的ESG分析报告。

报告应包含：
1. 执行摘要 - 2-3段话，总结主要发现
2. 关键发现 - 5-10个重点洞察
3. 风险预警 - 识别critical和high风险
4. 最佳实践 - 推荐优秀企业的实践

输出必须是标准JSON格式。"""

    def __init__(self):
        """初始化报告生成器"""
        self.scorer = ESGScoringFramework()
        self.visualizer = ESGVisualizer()

    def generate_daily_report(self, companies: List[str],
                             focus_on: Optional[str] = None) -> ESGReport:
        """
        生成日报：新闻摘要 + 风险预警
        - 关注新发生的ESG相关新闻
        - 快速风险预警
        - 简洁易读

        Args:
            companies: 关注公司列表
            focus_on: 特定关注的维度（E/S/G）
        """
        logger.info("[ReportGenerator] Generating daily report")

        report = ESGReport(
            report_type="daily",
            title="ESG 每日快报",
            period_start=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            period_end=datetime.now(),
            executive_summary="",
            key_findings=[],
            company_analyses=[],
            risk_alerts=[],
            best_practices=[],
            report_statistics={},
            visualizations={},
            generated_at=datetime.now(),
            data_sources=["scanner", "event_extractor", "risk_scorer"],
            confidence_score=0.85
        )

        try:
            # 从数据库获取最近24小时的事件
            from gateway.db.supabase_client import supabase_client

            events = supabase_client.table("extracted_events").select("*").gte(
                "created_at",
                (datetime.now() - timedelta(days=1)).isoformat()
            ).execute().data

            # 按公司过滤
            company_events = {}
            for company in companies:
                company_events[company] = [e for e in events if company.lower() in e.get("company", "").lower()]

            # 生成每个公司的分析
            for company_name, company_company_events in company_events.items():
                if not company_company_events:
                    continue

                analysis = CompanyAnalysis(
                    company_name=company_name,
                    esg_score=0.0,
                    trend="stable",
                    summary=f"有 {len(company_company_events)} 个新的ESG相关事件",
                    key_metrics={
                        "events_count": len(company_company_events),
                        "critical_count": len([e for e in company_company_events if e.get("severity") == "critical"]),
                    }
                )
                report.company_analyses.append(analysis)

            # 识别风险预警
            report.risk_alerts = self._extract_risk_alerts(events, threshold="high")

            # 生成执行摘要
            report.executive_summary = self._generate_summary(report)

            logger.info("[ReportGenerator] Daily report generated successfully")
            return report

        except Exception as e:
            logger.error(f"[ReportGenerator] Error generating daily report: {e}")
            report.executive_summary = f"报告生成出错: {str(e)}"
            return report

    def generate_weekly_report(self, companies: List[str]) -> ESGReport:
        """
        生成周报：评分变化 + 行业对标分析

        包含：
        - ESG评分变化趋势
        - 与同行业的对标对比
        - 周度风险热力图
        - 优秀实践案例
        """
        logger.info("[ReportGenerator] Generating weekly report")

        period_start = datetime.now() - timedelta(days=7)
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

        report = ESGReport(
            report_type="weekly",
            title="ESG 周度报告",
            period_start=period_start,
            period_end=datetime.now(),
            executive_summary="",
            key_findings=[],
            company_analyses=[],
            risk_alerts=[],
            best_practices=[],
            report_statistics={},
            visualizations={},
            generated_at=datetime.now(),
            data_sources=["esg_scorer", "data_sources", "news"],
            confidence_score=0.88
        )

        try:
            # 生成每个公司的ESG评分
            from gateway.scheduler.data_sources import DataSourceManager

            data_mgr = DataSourceManager()

            for company_name in companies:
                # 拉取数据
                company_data = data_mgr.fetch_company_data(company_name)

                # 评分
                esg_report = self.scorer.score_esg(company_name, company_data.dict())

                # 创建公司分析
                analysis = CompanyAnalysis(
                    company_name=company_name,
                    ticker=company_data.ticker,
                    esg_score=esg_report.overall_score,
                    trend=esg_report.overall_trend,
                    summary=esg_report.e_scores.summary[:200],  # 简化摘要
                    key_metrics={
                        "e_score": esg_report.e_scores.overall_score,
                        "s_score": esg_report.s_scores.overall_score,
                        "g_score": esg_report.g_scores.overall_score,
                    },
                    peer_rank=esg_report.peer_rank,
                )
                report.company_analyses.append(analysis)

            # 识别低分公司和优秀企业
            low_scores = [a for a in report.company_analyses if a.esg_score < 40]
            high_scores = [a for a in report.company_analyses if a.esg_score >= 80]

            if low_scores:
                report.key_findings.append(f"⚠️ {len(low_scores)}家企业ESG评分低于40分，需要重点关注")
            if high_scores:
                report.key_findings.append(f"✓ {len(high_scores)}家企业表现优秀，ESG评分80分以上")

            # 生成报告统计
            report.report_statistics = {
                "total_companies": len(companies),
                "average_score": sum(a.esg_score for a in report.company_analyses) / len(report.company_analyses) if report.company_analyses else 0,
                "high_performers": len(high_scores),
                "low_performers": len(low_scores),
            }

            # 生成执行摘要
            report.executive_summary = self._generate_summary(report)

            logger.info("[ReportGenerator] Weekly report generated successfully")
            return report

        except Exception as e:
            logger.error(f"[ReportGenerator] Error generating weekly report: {e}")
            report.executive_summary = f"报告生成出错: {str(e)}"
            return report

    def generate_monthly_report(self, portfolio: List[str]) -> ESGReport:
        """
        生成月报：投资组合视图 + 行业趋势分析

        包含：
        - 整体投资组合ESG评分
        - 高风险和优秀公司排名
        - 行业趋势和对标分析
        - 监管合规检查
        """
        logger.info("[ReportGenerator] Generating monthly report")

        period_start = datetime.now() - timedelta(days=30)
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

        report = ESGReport(
            report_type="monthly",
            title="ESG 月度投资组合报告",
            period_start=period_start,
            period_end=datetime.now(),
            executive_summary="",
            key_findings=[],
            company_analyses=[],
            risk_alerts=[],
            best_practices=[],
            report_statistics={},
            visualizations={},
            generated_at=datetime.now(),
            data_sources=["esg_scorer", "data_sources", "news", "sec_edgar"],
            confidence_score=0.90
        )

        try:
            from gateway.scheduler.data_sources import DataSourceManager

            data_mgr = DataSourceManager()

            all_analyses = []

            # 评分所有投资组合中的公司
            for company_name in portfolio:
                company_data = data_mgr.fetch_company_data(company_name)
                esg_report = self.scorer.score_esg(company_name, company_data.dict())

                analysis = CompanyAnalysis(
                    company_name=company_name,
                    ticker=company_data.ticker,
                    esg_score=esg_report.overall_score,
                    trend=esg_report.overall_trend,
                    summary=f"{esg_report.overall_score:.1f}/100",
                    key_metrics={
                        "e_score": esg_report.e_scores.overall_score,
                        "s_score": esg_report.s_scores.overall_score,
                        "g_score": esg_report.g_scores.overall_score,
                        "confidence": esg_report.confidence_score,
                    },
                    peer_rank=esg_report.peer_rank,
                )
                all_analyses.append(analysis)

            report.company_analyses = sorted(all_analyses, key=lambda x: x.esg_score, reverse=True)

            # 生成投资组合统计
            scores = [a.esg_score for a in report.company_analyses]
            report.report_statistics = {
                "portfolio_size": len(portfolio),
                "portfolio_average_score": sum(scores) / len(scores) if scores else 0,
                "portfolio_risk_rating": self._get_portfolio_risk_rating(scores),
                "top_performers": [a.company_name for a in report.company_analyses[:3]],
                "bottom_performers": [a.company_name for a in report.company_analyses[-3:]],
                "score_distribution": self._calculate_score_distribution(scores),
            }

            # 识别关键风险
            critical_issues = []
            for analysis in report.company_analyses:
                if analysis.esg_score < 30:
                    critical_issues.append(f"🔴 {analysis.company_name}: ESG评分极低 ({analysis.esg_score:.1f})")

            if critical_issues:
                report.key_findings.extend(critical_issues[:5])

            # 生成执行摘要
            report.executive_summary = self._generate_summary(report)

            logger.info("[ReportGenerator] Monthly report generated successfully")
            return report

        except Exception as e:
            logger.error(f"[ReportGenerator] Error generating monthly report: {e}")
            report.executive_summary = f"报告生成出错: {str(e)}"
            return report

    def _extract_risk_alerts(self, events: List[Dict], threshold: str = "high") -> List[RiskAlert]:
        """从事件列表提取风险预警"""
        alerts = []

        for event in events:
            severity = event.get("severity", "medium")
            if severity in ["critical", "high"]:
                alert = RiskAlert(
                    company=event.get("company", "Unknown"),
                    risk_level=severity,
                    category=event.get("impact_area", "G"),
                    title=event.get("title", ""),
                    description=event.get("description", ""),
                    impact=event.get("reasoning", "Potential business impact"),
                    recommendation=f"建议立即跟进并采取行动",
                    affected_areas=[event.get("impact_area", "G")],
                    alert_date=datetime.now(),
                )
                alerts.append(alert)

        return alerts[:10]  # 只返回前10个

    def _generate_summary(self, report: ESGReport) -> str:
        """生成执行摘要"""
        if report.report_type == "daily":
            return f"本日共发现 {len(report.company_analyses)} 家公司的ESG相关事件，其中 {len(report.risk_alerts)} 个高风险预警。"

        elif report.report_type == "weekly":
            avg_score = report.report_statistics.get("average_score", 0)
            return f"本周监控的{report.report_statistics.get('total_companies', 0)}家企业平均ESG评分为{avg_score:.1f}/100。"

        elif report.report_type == "monthly":
            portfolio_avg = report.report_statistics.get("portfolio_average_score", 0)
            return f"投资组合整体ESG评分为{portfolio_avg:.1f}/100，整体风险评级为{report.report_statistics.get('portfolio_risk_rating', 'Medium')}。"

        return ""

    @staticmethod
    def _get_portfolio_risk_rating(scores: List[float]) -> str:
        """根据评分分布计算投资组合风险评级"""
        if not scores:
            return "Unknown"

        avg = sum(scores) / len(scores)
        if avg >= 70:
            return "Low"
        elif avg >= 50:
            return "Medium"
        else:
            return "High"

    @staticmethod
    def _calculate_score_distribution(scores: List[float]) -> Dict[str, int]:
        """计算评分分布"""
        distribution = {
            "90_100": len([s for s in scores if s >= 90]),
            "70_89": len([s for s in scores if 70 <= s < 90]),
            "50_69": len([s for s in scores if 50 <= s < 70]),
            "30_49": len([s for s in scores if 30 <= s < 50]),
            "0_29": len([s for s in scores if s < 30]),
        }
        return distribution

    def generate_peer_comparison(self, target_company: str, peers: List[str]) -> Dict[str, Any]:
        """
        生成对标分析
        比较目标公司与竞争对手的ESG表现
        """
        logger.info(f"[ReportGenerator] Generating peer comparison for {target_company}")

        try:
            from gateway.scheduler.data_sources import DataSourceManager

            data_mgr = DataSourceManager()

            comparison = {
                "target": target_company,
                "peers": peers,
                "timestamp": datetime.now().isoformat(),
                "companies": {},
            }

            companies_to_analyze = [target_company] + peers

            for company_name in companies_to_analyze:
                company_data = data_mgr.fetch_company_data(company_name)
                esg_report = self.scorer.score_esg(company_name, company_data.dict())

                comparison["companies"][company_name] = {
                    "overall_score": esg_report.overall_score,
                    "e_score": esg_report.e_scores.overall_score,
                    "s_score": esg_report.s_scores.overall_score,
                    "g_score": esg_report.g_scores.overall_score,
                    "trend": esg_report.overall_trend,
                }

            # 计算排名
            sorted_companies = sorted(
                comparison["companies"].items(),
                key=lambda x: x[1]["overall_score"],
                reverse=True
            )

            comparison["ranking"] = [name for name, _ in sorted_companies]
            comparison["target_rank"] = comparison["ranking"].index(target_company) + 1 if target_company in comparison["ranking"] else None

            return comparison

        except Exception as e:
            logger.error(f"[ReportGenerator] Error generating peer comparison: {e}")
            return {}
