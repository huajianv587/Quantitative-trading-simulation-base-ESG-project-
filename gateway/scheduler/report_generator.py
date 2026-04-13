# report_generator.py — ESG 报告生成引擎
# 职责：根据收集的数据和评分结果，生成日/周/月ESG报告

import json
import importlib.util
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from gateway.utils.llm_client import chat
from gateway.utils.cache import get_cache, set_cache
from gateway.utils.logger import get_logger
from gateway.agents.esg_scorer import ESGScoringFramework, ESGScoreReport
from gateway.agents.esg_visualizer import ESGVisualizer
from gateway.rag.indexer import index_ready
from gateway.rag.rag_main import get_query_engine

logger = get_logger(__name__)
GROUNDING_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "have",
    "has",
    "been",
    "were",
    "will",
    "about",
    "company",
    "group",
    "report",
    "esg",
}


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
    grounding_status: Optional[str] = None
    grounding_confidence: Optional[float] = None
    verified_summary: Optional[str] = None
    verification_notes: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


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
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)


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
        self.report_cache_ttl_seconds = 900

    def _report_cache_key(self, report_type: str, companies: List[str]) -> str:
        normalized_companies = sorted(str(company).strip().upper() for company in companies if str(company).strip())
        bucket = datetime.utcnow().strftime("%Y-%m-%d")
        return f"esg_report::{report_type}::{bucket}::{','.join(normalized_companies)}"

    def _load_cached_report(self, report_type: str, companies: List[str]) -> Optional[ESGReport]:
        cached = get_cache(self._report_cache_key(report_type, companies))
        if not cached:
            return None
        try:
            return ESGReport.model_validate(cached)
        except Exception:
            return None

    def _store_cached_report(self, report: ESGReport, companies: List[str]) -> None:
        key = self._report_cache_key(report.report_type, companies)
        set_cache(
            key,
            report.model_dump(mode="json"),
            ttl_seconds=max(int(getattr(self, "report_cache_ttl_seconds", 900) or 900), 60),
        )

    @staticmethod
    def _clip_text(text: str, max_chars: int = 220) -> str:
        clean = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(clean) <= max_chars:
            return clean
        shortened = clean[:max_chars].rsplit(" ", 1)[0].strip()
        return f"{shortened or clean[:max_chars].strip()}..."

    @staticmethod
    def _keyword_set(text: str) -> set[str]:
        return {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{3,}", str(text or ""))
            if token.lower() not in GROUNDING_STOPWORDS
        }

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _grounding_cache_key(self, report_type: str, company_name: str, ticker: Optional[str]) -> str:
        return (
            f"esg_report_grounding::{report_type}::"
            f"{str(company_name or '').strip().lower()}::{str(ticker or '').strip().upper()}"
        )

    @staticmethod
    def _extract_node_content(node: Any) -> tuple[str, dict[str, Any], float]:
        score = 0.0
        metadata: dict[str, Any] = {}
        if hasattr(node, "score"):
            score = ESGReportGenerator._safe_float(getattr(node, "score"), 0.0)

        candidate = getattr(node, "node", node)
        if hasattr(candidate, "metadata") and isinstance(candidate.metadata, dict):
            metadata = dict(candidate.metadata)
        elif hasattr(node, "metadata") and isinstance(node.metadata, dict):
            metadata = dict(node.metadata)

        if hasattr(candidate, "get_content"):
            content = candidate.get_content()
        elif hasattr(node, "get_content"):
            content = node.get_content()
        else:
            content = str(node)
        return str(content or ""), metadata, score

    @staticmethod
    def _infer_source_type(source: str) -> str:
        lower = str(source or "").lower()
        if "sec" in lower:
            return "sec_filing"
        if "news" in lower or "finnhub" in lower:
            return "news"
        if "scheduler" in lower:
            return "event"
        if lower:
            return "rag_doc"
        return "unknown"

    def _collect_rag_citations(
        self,
        *,
        company_name: str,
        ticker: Optional[str],
        report_type: str,
    ) -> List[Dict[str, Any]]:
        if importlib.util.find_spec("qdrant_client") is None:
            return []
        if not index_ready():
            return []
        query = f"{company_name} {ticker or ''} {report_type} ESG governance environmental social controversies"
        try:
            response = get_query_engine().query(query)
        except Exception as exc:
            logger.warning(f"[ReportGenerator] Grounding retrieval failed for {company_name}: {exc}")
            return []

        citations: List[Dict[str, Any]] = []
        for index, node in enumerate(getattr(response, "source_nodes", []) or []):
            content, metadata, score = self._extract_node_content(node)
            if not content:
                continue
            source = (
                metadata.get("source")
                or metadata.get("file_name")
                or metadata.get("path")
                or metadata.get("doc_id")
                or f"RAG chunk {index + 1}"
            )
            citations.append(
                {
                    "label": "retrieval",
                    "source": source,
                    "source_type": self._infer_source_type(str(source)),
                    "snippet": self._clip_text(content, 260),
                    "url": metadata.get("url") or metadata.get("source_url"),
                    "filed_at": metadata.get("created_at") or metadata.get("date"),
                    "base_score": round(score, 6),
                }
            )
        return citations

    def _rerank_citations(
        self,
        *,
        company_name: str,
        ticker: Optional[str],
        summary: str,
        citations: List[Dict[str, Any]],
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        if not citations:
            return []

        company_terms = self._keyword_set(f"{company_name} {ticker or ''}")
        summary_terms = self._keyword_set(summary)
        ranked: List[Dict[str, Any]] = []
        for item in citations:
            snippet = str(item.get("snippet") or "")
            source = str(item.get("source") or "")
            text_terms = self._keyword_set(f"{snippet} {source}")
            company_overlap = len(company_terms & text_terms)
            summary_overlap = len(summary_terms & text_terms)
            score = self._safe_float(item.get("base_score"), 0.0)
            score += company_overlap * 1.4
            score += summary_overlap * 0.8
            if company_name.lower() in snippet.lower():
                score += 0.75
            if ticker and ticker.lower() in snippet.lower():
                score += 0.45
            if item.get("source_type") == "sec_filing":
                score += 0.55
            if item.get("source_type") == "news":
                score += 0.30
            ranked.append({**item, "relevance": round(score, 4)})

        ranked.sort(key=lambda item: item.get("relevance", 0.0), reverse=True)
        return ranked[:limit]

    def _verify_citations(self, summary: str, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not summary:
            return {
                "status": "missing",
                "confidence": 0.0,
                "notes": ["No summary was available for citation verification."],
                "verified_summary": "",
            }
        if not citations:
            return {
                "status": "missing",
                "confidence": 0.0,
                "notes": ["No citations were retrieved for this analysis."],
                "verified_summary": summary,
            }

        citation_terms = self._keyword_set(" ".join(str(item.get("snippet") or "") for item in citations))
        sentences = [item.strip() for item in re.split(r"(?<=[.!?。；;])\s+", summary) if item.strip()]
        coverage_scores: List[float] = []
        notes: List[str] = []
        for sentence in sentences or [summary]:
            lowered = sentence.lower()
            if "screens at" in lowered or "/100" in lowered or "esg trend" in lowered:
                continue
            keywords = self._keyword_set(sentence)
            if not keywords:
                continue
            overlap = len(keywords & citation_terms)
            coverage = overlap / max(len(keywords), 1)
            coverage_scores.append(coverage)
            if coverage < 0.45:
                notes.append(f"Weak citation coverage for: {self._clip_text(sentence, 90)}")

        confidence = round(sum(coverage_scores) / max(len(coverage_scores), 1), 4)
        if confidence >= 0.65:
            status = "grounded"
        elif confidence >= 0.4:
            status = "partial"
        else:
            status = "weak"

        return {
            "status": status,
            "confidence": confidence,
            "notes": notes,
            "verified_summary": summary,
        }

    def _build_grounding_bundle(
        self,
        *,
        company_name: str,
        ticker: Optional[str],
        report_type: str,
        summary: str,
        company_data: Any,
    ) -> Dict[str, Any]:
        cache_key = self._grounding_cache_key(report_type, company_name, ticker)
        cached = get_cache(cache_key)
        if isinstance(cached, dict):
            return cached

        candidates: List[Dict[str, Any]] = []
        candidates.extend(self._collect_rag_citations(company_name=company_name, ticker=ticker, report_type=report_type))

        for item in (getattr(company_data, "recent_news", None) or [])[:4]:
            snippet = item.get("description") or item.get("content") or item.get("title")
            if not snippet:
                continue
            candidates.append(
                {
                    "label": "news",
                    "source": item.get("source") or "News",
                    "source_type": "news",
                    "snippet": self._clip_text(snippet, 240),
                    "url": item.get("url"),
                    "filed_at": item.get("published_at"),
                    "base_score": 0.35,
                }
            )

        governance = getattr(company_data, "governance", {}) or {}
        for item in governance.get("sec_governance_evidence", [])[:4]:
            snippet = item.get("snippet")
            if not snippet:
                continue
            candidates.append(
                {
                    "label": item.get("label") or "sec_evidence",
                    "source": item.get("source") or f"SEC {item.get('form') or 'filing'}",
                    "source_type": "sec_filing",
                    "snippet": self._clip_text(snippet, 240),
                    "url": item.get("url"),
                    "filed_at": item.get("filed_at"),
                    "base_score": 0.6,
                }
            )

        citations = self._rerank_citations(
            company_name=company_name,
            ticker=ticker,
            summary=summary,
            citations=candidates,
            limit=4,
        )
        verification = self._verify_citations(summary, citations)
        bundle = {
            "query": f"{company_name} {ticker or ''} {report_type} ESG evidence",
            "citations": citations,
            "grounding_status": verification["status"],
            "grounding_confidence": verification["confidence"],
            "verification_notes": verification["notes"],
            "verified_summary": verification["verified_summary"],
            "citation_count": len(citations),
            "retrieval_stack": "hybrid_bm25_vector_plus_news_sec",
        }
        set_cache(cache_key, bundle, ttl_seconds=600)
        return bundle

    def _attach_grounding(self, analysis: CompanyAnalysis, *, report_type: str, company_data: Any) -> CompanyAnalysis:
        bundle = self._build_grounding_bundle(
            company_name=analysis.company_name,
            ticker=analysis.ticker,
            report_type=report_type,
            summary=analysis.summary,
            company_data=company_data,
        )
        return analysis.model_copy(
            update={
                "grounding_status": bundle.get("grounding_status"),
                "grounding_confidence": bundle.get("grounding_confidence"),
                "verified_summary": bundle.get("verified_summary"),
                "verification_notes": bundle.get("verification_notes") or [],
                "citations": bundle.get("citations") or [],
            }
        )

    def _compose_company_summary(self, company_name: str, company_data: Any, esg_report: ESGScoreReport) -> str:
        parts = [f"{company_name} screens at {esg_report.overall_score:.1f}/100 with a {esg_report.overall_trend} ESG trend."]
        recent_news = (getattr(company_data, "recent_news", None) or [])[:1]
        if recent_news:
            lead = recent_news[0]
            headline = lead.get("title") or lead.get("description") or lead.get("content")
            if headline:
                parts.append(f"Recent news signal: {self._clip_text(headline, 120)}")
        governance = getattr(company_data, "governance", {}) or {}
        sec_evidence = (governance.get("sec_governance_evidence") or [])[:1]
        if sec_evidence:
            parts.append(f"SEC governance evidence: {self._clip_text(sec_evidence[0].get('snippet') or '', 120)}")
        return " ".join(part for part in parts if part).strip()

    def _finalize_grounding_summary(self, report: ESGReport) -> None:
        analyses = list(report.company_analyses or [])
        citation_count = sum(len(item.citations or []) for item in analyses)
        grounded = sum(1 for item in analyses if item.grounding_status == "grounded")
        average_confidence = (
            round(
                sum(float(item.grounding_confidence or 0.0) for item in analyses) / len(analyses),
                4,
            )
            if analyses
            else 0.0
        )
        report.evidence_summary = {
            "grounded_companies": grounded,
            "total_companies": len(analyses),
            "citation_count": citation_count,
            "average_grounding_confidence": average_confidence,
            "retrieval_stack": "hybrid_bm25_vector_plus_news_sec",
            "verification_mode": "deterministic_citation_overlap",
        }

    def _apply_grounding_data_sources(self, report: ESGReport) -> None:
        sources = set(report.data_sources or [])
        citation_source_types = {
            str(citation.get("source_type") or "").strip().lower()
            for analysis in report.company_analyses or []
            for citation in analysis.citations or []
        }
        if "news" in citation_source_types:
            sources.add("news")
        if "sec_filing" in citation_source_types:
            sources.add("sec_edgar")
        if "rag_doc" in citation_source_types or "event" in citation_source_types:
            sources.add("qdrant_hybrid")
        report.data_sources = sorted(source for source in sources if source)

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
        cached = self._load_cached_report("daily", companies)
        if cached is not None:
            return cached

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
            from gateway.scheduler.data_sources import DataSourceManager

            data_mgr = DataSourceManager()
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

                company_data = data_mgr.fetch_company_data(company_name)
                leading_event = company_company_events[0]
                analysis = CompanyAnalysis(
                    company_name=company_name,
                    ticker=company_data.ticker,
                    esg_score=0.0,
                    trend="stable",
                    summary=(
                        f"{company_name} had {len(company_company_events)} fresh ESG events in the last 24h. "
                        f"Priority topic: {leading_event.get('title') or leading_event.get('description') or 'event monitor'}."
                    ),
                    key_metrics={
                        "events_count": len(company_company_events),
                        "critical_count": len([e for e in company_company_events if e.get("severity") == "critical"]),
                    }
                )
                report.company_analyses.append(self._attach_grounding(analysis, report_type="daily", company_data=company_data))

            # 识别风险预警
            report.risk_alerts = self._extract_risk_alerts(events, threshold="high")

            # 生成执行摘要
            report.executive_summary = self._generate_summary(report)
            self._finalize_grounding_summary(report)
            self._apply_grounding_data_sources(report)
            self._store_cached_report(report, companies)

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
        cached = self._load_cached_report("weekly", companies)
        if cached is not None:
            return cached

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
                esg_report = self.scorer.score_esg(company_name, company_data.model_dump(), prefer_fast_mode=True)

                # 创建公司分析
                analysis = CompanyAnalysis(
                    company_name=company_name,
                    ticker=company_data.ticker,
                    esg_score=esg_report.overall_score,
                    trend=esg_report.overall_trend,
                    summary=self._compose_company_summary(company_name, company_data, esg_report),
                    key_metrics={
                        "e_score": esg_report.e_scores.overall_score,
                        "s_score": esg_report.s_scores.overall_score,
                        "g_score": esg_report.g_scores.overall_score,
                    },
                    peer_rank=esg_report.peer_rank,
                )
                report.company_analyses.append(self._attach_grounding(analysis, report_type="weekly", company_data=company_data))

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
            self._finalize_grounding_summary(report)
            self._apply_grounding_data_sources(report)
            self._store_cached_report(report, companies)

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
        cached = self._load_cached_report("monthly", portfolio)
        if cached is not None:
            return cached

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
                esg_report = self.scorer.score_esg(company_name, company_data.model_dump(), prefer_fast_mode=True)

                analysis = CompanyAnalysis(
                    company_name=company_name,
                    ticker=company_data.ticker,
                    esg_score=esg_report.overall_score,
                    trend=esg_report.overall_trend,
                    summary=self._compose_company_summary(company_name, company_data, esg_report),
                    key_metrics={
                        "e_score": esg_report.e_scores.overall_score,
                        "s_score": esg_report.s_scores.overall_score,
                        "g_score": esg_report.g_scores.overall_score,
                        "confidence": esg_report.confidence_score,
                    },
                    peer_rank=esg_report.peer_rank,
                )
                all_analyses.append(self._attach_grounding(analysis, report_type="monthly", company_data=company_data))

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
            self._finalize_grounding_summary(report)
            self._apply_grounding_data_sources(report)
            self._store_cached_report(report, portfolio)

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
                esg_report = self.scorer.score_esg(company_name, company_data.model_dump(), prefer_fast_mode=True)

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
