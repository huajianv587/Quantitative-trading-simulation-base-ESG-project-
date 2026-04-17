# esg_scorer.py — ESG 结构化评分框架
# 职责：基于检索到的 ESG 数据，生成结构化的 E/S/G 15维度评分
# 包含：碳排放、能源效率、水资源、废物、可再生能源（E）
#      员工满意度、多样性、供应链伦理、社区关系、客户保护（S）
#      董事会多样性、高管薪酬、反腐机制、风险管理、股东权益（G）

import json
import re
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from gateway.config import settings
from gateway.quant.esg_house_score import FORMULA_VERSION, compute_house_score
from gateway.utils.llm_client import chat
from gateway.utils.cache import get_cache, set_cache
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────────────────
class ESGMetric(BaseModel):
    """单个ESG指标"""
    name: str
    score: float  # 0-100
    weight: float  # 权重
    reasoning: str
    trend: Optional[str] = None  # "up", "down", "stable"
    data_source: Optional[str] = None


class ESGDimensionScores(BaseModel):
    """ESG单个维度的评分"""
    dimension: str  # "E", "S", "G"
    overall_score: float  # 0-100
    metrics: Dict[str, ESGMetric]
    summary: str


class ESGScoreReport(BaseModel):
    """完整的ESG评分报告"""
    company_name: str
    ticker: Optional[str] = None
    industry: Optional[str] = None

    # 三维评分
    e_scores: ESGDimensionScores
    s_scores: ESGDimensionScores
    g_scores: ESGDimensionScores

    # 综合评分
    overall_score: float  # 0-100
    overall_trend: str  # "up", "down", "stable"

    # 对标排名
    peer_rank: Optional[str] = None  # "top 20%", "average", etc
    industry_position: Optional[str] = None

    # 推理和建议
    key_strengths: List[str]
    key_weaknesses: List[str]
    recommendations: List[str]

    # 元数据
    assessment_date: datetime
    data_sources: List[str]
    confidence_score: float  # 0-1
    historical_data: Optional[Dict[str, Any]] = None
    house_score: float = 0.0
    house_grade: str = "CCC"
    formula_version: str = FORMULA_VERSION
    pillar_breakdown: Dict[str, float] = {}
    disclosure_confidence: float = 0.0
    controversy_penalty: float = 0.0
    data_gap_penalty: float = 0.0
    materiality_adjustment: float = 0.0
    trend_bonus: float = 0.0
    house_explanation: str = ""


# ── ESG 评分框架 ──────────────────────────────────────────────────────────

class ESGScoringFramework:
    """
    结构化的ESG评分框架
    - 15个明确的指标（E/S/G各5个）
    - 每个指标有权重和评分逻辑
    - 支持行业对标和历史比较
    """

    # E维度指标定义
    E_METRICS = {
        "carbon_emissions": {
            "name": "碳排放强度",
            "weight": 0.25,
            "unit": "tCO2e/百万收入",
            "description": "企业碳排放相对收入的比值"
        },
        "energy_efficiency": {
            "name": "能源效率",
            "weight": 0.20,
            "unit": "MWh/产出单位",
            "description": "单位产出所需能源"
        },
        "water_management": {
            "name": "水资源管理",
            "weight": 0.15,
            "unit": "千升/产出单位",
            "description": "水消耗和循环利用比例"
        },
        "waste_management": {
            "name": "废物管理",
            "weight": 0.20,
            "unit": "回收率%",
            "description": "废物回收和减量目标达成度"
        },
        "renewable_energy": {
            "name": "可再生能源使用",
            "weight": 0.20,
            "unit": "% of total",
            "description": "可再生能源占总能源的比例"
        }
    }

    # S维度指标定义
    S_METRICS = {
        "employee_satisfaction": {
            "name": "员工满意度",
            "weight": 0.20,
            "unit": "eNPS score",
            "description": "员工净推荐值和满意度调查"
        },
        "diversity_inclusion": {
            "name": "多样性与包容性",
            "weight": 0.25,
            "unit": "% women/minorities",
            "description": "女性和少数族裔员工占比、高管中占比"
        },
        "supply_chain_ethics": {
            "name": "供应链伦理",
            "weight": 0.20,
            "unit": "合规率%",
            "description": "供应商审计通过率、劳动标准合规"
        },
        "community_relations": {
            "name": "社区关系",
            "weight": 0.15,
            "unit": "投资额/社会影响指数",
            "description": "社区投资、本地就业、社会贡献"
        },
        "customer_protection": {
            "name": "客户保护",
            "weight": 0.20,
            "unit": "投诉率/满意度",
            "description": "数据隐私、产品安全、客户满意度"
        }
    }

    # G维度指标定义
    G_METRICS = {
        "board_diversity": {
            "name": "董事会多样性",
            "weight": 0.20,
            "unit": "% 独立董事",
            "description": "独立董事占比、女性董事占比、任期多样性"
        },
        "executive_pay_ratio": {
            "name": "高管薪酬合理性",
            "weight": 0.20,
            "unit": "倍数",
            "description": "CEO薪酬与员工中位数薪酬的比例"
        },
        "anti_corruption": {
            "name": "反腐机制",
            "weight": 0.20,
            "unit": "得分/10",
            "description": "反腐政策完整性、举报机制、违规处罚"
        },
        "risk_management": {
            "name": "风险管理",
            "weight": 0.20,
            "unit": "评级",
            "description": "风险管理框架、网络安全、业务连续性"
        },
        "shareholder_rights": {
            "name": "股东权益保护",
            "weight": 0.20,
            "unit": "得分/10",
            "description": "股东投票权、信息披露透明度、董事选举机制"
        }
    }

    SYSTEM_PROMPT = """你是一个专业的ESG评分分析师。
根据提供的企业数据和报告，你需要生成一份结构化的ESG评分报告。

评分规则：
1. 每个指标评分范围 0-100
2. 评分依据必须明确：使用具体的数据和对标数据
3. 如果数据不足，应该说明并给出保守估计
4. 趋势分析：对比历年数据，判断 up/down/stable
5. 对标分析：与同行业、同规模企业对比，给出相对位置

输出必须是标准JSON格式，包含：
{
    "e_scores": {
        "overall_score": 0-100,
        "metrics": {
            "carbon_emissions": { "score": 0-100, "reasoning": "..." },
            ...
        },
        "summary": "..."
    },
    "s_scores": { ... },
    "g_scores": { ... },
    "overall_score": 0-100,
    "overall_trend": "up/down/stable",
    "key_strengths": [...],
    "key_weaknesses": [...],
    "recommendations": [...]
}"""

    def __init__(self, llm_model: str = "claude"):
        """初始化评分框架"""
        self.llm_model = llm_model
        self.metrics_cache = {}

    def _live_llm_ready(self) -> bool:
        backend_mode = str(getattr(settings, "LLM_BACKEND_MODE", "auto") or "auto").strip().lower()
        if backend_mode != "remote":
            return True

        base_url = str(getattr(settings, "REMOTE_LLM_URL", "") or "").strip()
        if not base_url:
            return False

        cache_key = f"esg_remote_health::{base_url.rstrip('/')}"
        cached = get_cache(cache_key)
        if cached is not None:
            return bool(cached)

        try:
            response = requests.get(
                f"{base_url.rstrip('/')}/health",
                timeout=max(float(getattr(settings, "REMOTE_LLM_HEALTH_TIMEOUT", 2.0) or 2.0), 0.5),
            )
            ready = response.ok
        except Exception:
            ready = False

        set_cache(
            cache_key,
            ready,
            ttl_seconds=max(int(getattr(settings, "REMOTE_LLM_HEALTH_TTL_SECONDS", 30) or 30), 5),
        )
        return ready

    def score_esg(self, company_name: str, esg_data: Dict[str, Any],
                  peers: Optional[List[str]] = None,
                  include_history: bool = False,
                  prefer_fast_mode: bool = False) -> ESGScoreReport:
        """
        生成完整的ESG评分报告

        Args:
            company_name: 公司名称
            esg_data: ESG相关数据（从DataSourceManager获取）
            peers: 对标公司列表
            include_history: 是否包含历史数据

        Returns:
            ESGScoreReport: 完整的评分报告
        """
        logger.info(f"[ESGScorer] Starting ESG scoring for {company_name}")
        cache_key = json.dumps(
            {
                "company": company_name,
                "peers": peers or [],
                "include_history": include_history,
                "payload": esg_data,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        cached = self.metrics_cache.get(cache_key) or get_cache(f"esg_score::{cache_key}")
        if cached:
            if isinstance(cached, ESGScoreReport):
                return cached
            try:
                report = ESGScoreReport.model_validate(cached)
                self.metrics_cache[cache_key] = report
                return report
            except Exception:
                pass

        try:
            # 准备用于LLM的数据摘要
            data_summary = self._prepare_data_summary(company_name, esg_data, peers)

            # 调用LLM进行评分
            try:
                backend_mode = str(getattr(settings, "LLM_BACKEND_MODE", "auto") or "auto").strip().lower()
                if prefer_fast_mode and backend_mode == "cloud":
                    raise RuntimeError("Fast-mode report scoring prefers deterministic structured fallback in cloud mode")
                if not self._live_llm_ready():
                    raise RuntimeError("Remote ESG LLM service is unavailable")
                raw_response = chat(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": data_summary}
                ],
                temperature=0.2,
                max_tokens=800
            )

            # 解析JSON响应
                scores_data = self._parse_llm_response(raw_response, company_name, esg_data)
            except Exception as exc:
                logger.warning(f"[ESGScorer] LLM unavailable, using heuristic fallback for {company_name}: {exc}")
                scores_data = self._build_fallback_scores(
                    company_name,
                    esg_data,
                    f"LLM unavailable: {exc}",
                )

            # 构建报告对象
            report = self._build_report(company_name, esg_data, scores_data)
            if len(self.metrics_cache) >= 128:
                self.metrics_cache.pop(next(iter(self.metrics_cache)))
            self.metrics_cache[cache_key] = report
            set_cache(f"esg_score::{cache_key}", report.model_dump(mode="json"), ttl_hours=6)

            logger.info(f"[ESGScorer] Completed ESG scoring: {company_name} score={report.overall_score}")
            return report

        except Exception as e:
            logger.error(f"[ESGScorer] Error scoring {company_name}: {e}")
            raise

    def _prepare_data_summary(self, company_name: str, esg_data: Dict[str, Any],
                             peers: Optional[List[str]] = None) -> str:
        """准备用于LLM的数据摘要"""
        summary = f"""
【企业评分请求】
企业名称: {company_name}
行业: {esg_data.get('industry', 'Unknown')}
市值: {esg_data.get('market_cap', 'Unknown')}
员工数: {esg_data.get('employees', 'Unknown')}

【环境(E)相关数据】
{self._format_data_section(esg_data.get('environmental', {}))}

【社会(S)相关数据】
{self._format_data_section(esg_data.get('social', {}))}

【治理(G)相关数据】
{self._format_data_section(esg_data.get('governance', {}))}

【财务数据】
{self._format_data_section(esg_data.get('financial', {}))}

【外部评分参考】
{self._format_data_section(esg_data.get('external_ratings', {}))}

{"【对标公司】" + ", ".join(peers) if peers else ""}
"""
        return summary

    def _format_data_section(self, data: Dict[str, Any]) -> str:
        """格式化数据段"""
        if not data:
            return "无数据"

        lines = []
        for index, (key, value) in enumerate(data.items()):
            if index >= 8:
                lines.append("  - ... additional structured fields omitted for latency control")
                break
            if isinstance(value, dict):
                lines.append(f"  {key}:")
                for nested_index, (k, v) in enumerate(value.items()):
                    if nested_index >= 4:
                        lines.append("    - ...")
                        break
                    lines.append(f"    - {k}: {self._truncate_value(v)}")
            elif isinstance(value, list):
                preview = ", ".join(self._truncate_value(item) for item in value[:3])
                lines.append(f"  - {key}: [{preview}{', ...' if len(value) > 3 else ''}]")
            else:
                lines.append(f"  - {key}: {self._truncate_value(value)}")
        return "\n".join(lines)

    @staticmethod
    def _truncate_value(value: Any, max_chars: int = 120) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= max_chars:
            return text
        shortened = text[:max_chars].rsplit(" ", 1)[0].strip()
        return f"{shortened or text[:max_chars].strip()}..."

    def _parse_llm_response(self, response: str, company_name: str, esg_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析LLM返回的JSON，必要时退化为启发式结构化结果"""
        text = response.strip()
        try:
            # 去掉markdown代码块
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            return json.loads(text)
        except json.JSONDecodeError as e:
            json_match = re.search(r"(\{[\s\S]*\})", text)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            logger.warning(f"[ESGScorer] JSON parse error, switching to heuristic fallback: {e}")
            return self._build_fallback_scores(company_name, esg_data, text)

    def _build_fallback_scores(self, company_name: str, esg_data: Dict[str, Any], raw_response: str) -> Dict[str, Any]:
        """在无JSON输出时生成保守但完整的ESG结构化结果"""
        source_count = len(esg_data.get("data_sources", []))
        external = esg_data.get("external_ratings", {}) or {}
        environmental = esg_data.get("environmental", {}) or {}
        social = esg_data.get("social", {}) or {}
        governance = esg_data.get("governance", {}) or {}

        base_score = 58 + min(source_count * 2, 8)
        external_bias = self._extract_numeric_signal(external)
        if external_bias is not None:
            base_score = max(35, min(88, int(external_bias)))

        e_score = self._derive_dimension_score(base_score, environmental, positive_hints=("renewable", "reduction", "efficiency", "water"))
        s_score = self._derive_dimension_score(base_score - 1, social, positive_hints=("safety", "diversity", "community", "training"))
        g_score = self._derive_dimension_score(base_score + 1, governance, positive_hints=("board", "audit", "compliance", "transparency"))
        overall_score = round(e_score * 0.35 + s_score * 0.33 + g_score * 0.32, 1)
        raw_summary = raw_response.strip() or f"{company_name} fallback assessment generated without live JSON output."

        return {
            "e_scores": self._build_fallback_dimension_payload(
                self.E_METRICS,
                environmental,
                e_score,
                "Environmental score estimated from available disclosures and fallback heuristics.",
            ),
            "s_scores": self._build_fallback_dimension_payload(
                self.S_METRICS,
                social,
                s_score,
                "Social score estimated from workforce, community, and safety signals in fallback mode.",
            ),
            "g_scores": self._build_fallback_dimension_payload(
                self.G_METRICS,
                governance,
                g_score,
                "Governance score estimated from board, policy, and disclosure signals in fallback mode.",
            ),
            "overall_score": overall_score,
            "overall_trend": "stable",
            "peer_rank": "provisional",
            "industry_position": "fallback estimate",
            "key_strengths": self._build_strengths(company_name, e_score, s_score, g_score),
            "key_weaknesses": self._build_weaknesses(e_score, s_score, g_score),
            "recommendations": self._build_recommendations(e_score, s_score, g_score),
            "fallback_summary": raw_summary[:300],
        }

    @staticmethod
    def _extract_numeric_signal(payload: Dict[str, Any]) -> Optional[float]:
        for value in payload.values():
            if isinstance(value, (int, float)) and 0 <= float(value) <= 100:
                return float(value)
            if isinstance(value, str):
                cleaned = value.replace("%", "").strip()
                try:
                    numeric = float(cleaned)
                except ValueError:
                    continue
                if 0 <= numeric <= 100:
                    return numeric
        return None

    @staticmethod
    def _derive_dimension_score(base_score: float, payload: Dict[str, Any], positive_hints: tuple[str, ...]) -> int:
        score = float(base_score)
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        score += sum(3 for hint in positive_hints if hint in serialized)
        score += min(len(payload) * 1.5, 6)
        return max(32, min(90, int(round(score))))

    def _build_fallback_dimension_payload(
        self,
        metrics_def: Dict[str, Dict[str, Any]],
        payload: Dict[str, Any],
        dimension_score: int,
        summary: str,
    ) -> Dict[str, Any]:
        metrics = {}
        serialized = json.dumps(payload, ensure_ascii=False)[:180] if payload else "Limited structured data available."
        for index, metric_key in enumerate(metrics_def.keys()):
            metric_score = max(30, min(92, dimension_score + 4 - index * 2))
            metrics[metric_key] = {
                "score": metric_score,
                "reasoning": f"Fallback estimate based on available company disclosures. Evidence snapshot: {serialized}",
                "trend": "stable",
                "data_source": "heuristic_fallback",
            }
        return {
            "overall_score": dimension_score,
            "metrics": metrics,
            "summary": summary,
        }

    @staticmethod
    def _build_strengths(company_name: str, e_score: float, s_score: float, g_score: float) -> List[str]:
        ranked = sorted(
            [
                ("environmental execution", e_score),
                ("social stewardship", s_score),
                ("governance discipline", g_score),
            ],
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            f"{company_name} shows comparatively stronger {ranked[0][0]} in the current fallback assessment.",
            f"Disclosure coverage supports a provisional {ranked[1][0]} reading.",
        ]

    @staticmethod
    def _build_weaknesses(e_score: float, s_score: float, g_score: float) -> List[str]:
        ranked = sorted(
            [
                ("environmental data depth", e_score),
                ("social program clarity", s_score),
                ("governance transparency", g_score),
            ],
            key=lambda item: item[1],
        )
        return [
            f"{ranked[0][0]} remains the least certain area and needs richer live-source evidence.",
            "This report was generated in fallback mode, so peer benchmarking confidence is limited.",
        ]

    @staticmethod
    def _build_recommendations(e_score: float, s_score: float, g_score: float) -> List[str]:
        recommendations = [
            "Reconnect a live LLM backend to replace heuristic fallback scoring with evidence-grounded structured analysis.",
            "Expand direct ESG disclosures and third-party source coverage before using this score for production investment decisions.",
        ]
        weakest = min(
            [("environmental", e_score), ("social", s_score), ("governance", g_score)],
            key=lambda item: item[1],
        )[0]
        recommendations.append(f"Prioritize additional data collection for the {weakest} dimension.")
        return recommendations

    @staticmethod
    def _metric_coverage_ratio(scores_data: Dict[str, Any]) -> float:
        total = 0
        populated = 0
        for dimension_key in ("e_scores", "s_scores", "g_scores"):
            metric_scores = (scores_data.get(dimension_key) or {}).get("metrics", {}) or {}
            for metric_payload in metric_scores.values():
                total += 1
                if isinstance(metric_payload, dict) and (
                    metric_payload.get("score") is not None
                    or metric_payload.get("reasoning")
                    or metric_payload.get("data_source")
                ):
                    populated += 1
        if total <= 0:
            return 0.0
        return populated / total

    def _build_report(self, company_name: str, esg_data: Dict[str, Any],
                     scores_data: Dict[str, Any]) -> ESGScoreReport:
        """构建ESGScoreReport对象"""

        e_metrics = self._build_dimension_scores(
            "E",
            scores_data.get("e_scores", {}),
            self.E_METRICS
        )

        s_metrics = self._build_dimension_scores(
            "S",
            scores_data.get("s_scores", {}),
            self.S_METRICS
        )

        g_metrics = self._build_dimension_scores(
            "G",
            scores_data.get("g_scores", {}),
            self.G_METRICS
        )

        metric_coverage_ratio = self._metric_coverage_ratio(scores_data)
        house_breakdown = compute_house_score(
            company_name=company_name,
            sector=esg_data.get("sector"),
            industry=esg_data.get("industry"),
            e_score=e_metrics.overall_score,
            s_score=s_metrics.overall_score,
            g_score=g_metrics.overall_score,
            data_sources=list(esg_data.get("data_sources") or []),
            data_lineage=list(esg_data.get("data_lineage") or []),
            recent_news=list(esg_data.get("recent_news") or []),
            controversy_hints=list(esg_data.get("controversies") or scores_data.get("key_weaknesses") or []),
            esg_delta=esg_data.get("esg_delta"),
            historical_data=esg_data.get("historical_data"),
            metric_coverage_ratio=metric_coverage_ratio,
        ).as_dict()

        return ESGScoreReport(
            company_name=company_name,
            ticker=esg_data.get("ticker"),
            industry=esg_data.get("industry"),
            e_scores=e_metrics,
            s_scores=s_metrics,
            g_scores=g_metrics,
            overall_score=scores_data.get("overall_score", 50),
            overall_trend=scores_data.get("overall_trend", "stable"),
            peer_rank=scores_data.get("peer_rank"),
            industry_position=scores_data.get("industry_position"),
            key_strengths=scores_data.get("key_strengths", []),
            key_weaknesses=scores_data.get("key_weaknesses", []),
            recommendations=scores_data.get("recommendations", []),
            assessment_date=datetime.now(),
            data_sources=esg_data.get("data_sources", []),
            confidence_score=min(0.95, 0.7 + len(esg_data.get("data_sources", [])) * 0.1),
            historical_data=esg_data.get("historical_data"),
            house_score=float(house_breakdown["house_score"]),
            house_grade=str(house_breakdown["house_grade"]),
            formula_version=str(house_breakdown["formula_version"]),
            pillar_breakdown=dict(house_breakdown["pillar_breakdown"]),
            disclosure_confidence=float(house_breakdown["disclosure_confidence"]),
            controversy_penalty=float(house_breakdown["controversy_penalty"]),
            data_gap_penalty=float(house_breakdown["data_gap_penalty"]),
            materiality_adjustment=float(house_breakdown["materiality_adjustment"]),
            trend_bonus=float(house_breakdown["trend_bonus"]),
            house_explanation=str(house_breakdown["house_explanation"]),
        )

    def _build_dimension_scores(self, dimension: str, scores_data: Dict,
                                metrics_def: Dict) -> ESGDimensionScores:
        """构建单个维度的评分"""
        metrics = {}
        metric_scores = scores_data.get("metrics", {})

        for metric_key, metric_def in metrics_def.items():
            score_data = metric_scores.get(metric_key, {})
            metrics[metric_key] = ESGMetric(
                name=metric_def["name"],
                score=score_data.get("score", 50),
                weight=metric_def["weight"],
                reasoning=score_data.get("reasoning", "Data insufficient"),
                trend=score_data.get("trend", "stable"),
                data_source=score_data.get("data_source")
            )

        overall = sum(m.score * m.weight for m in metrics.values())

        return ESGDimensionScores(
            dimension=dimension,
            overall_score=overall,
            metrics=metrics,
            summary=scores_data.get("summary", "")
        )

    def get_score_explanation(self, report: ESGScoreReport) -> str:
        """生成易读的评分解释"""
        return f"""
ESG 评分报告 - {report.company_name}
{'='*50}

综合评分: {report.overall_score:.1f}/100 ({self._get_rating_text(report.overall_score)})
趋势: {report.overall_trend}

━ 环境维度 (E): {report.e_scores.overall_score:.1f}/100
{report.e_scores.summary}

━ 社会维度 (S): {report.s_scores.overall_score:.1f}/100
{report.s_scores.summary}

━ 治理维度 (G): {report.g_scores.overall_score:.1f}/100
{report.g_scores.summary}

━ 核心优势:
{chr(10).join("  • " + s for s in report.key_strengths)}

━ 主要改进方向:
{chr(10).join("  • " + w for w in report.key_weaknesses)}

━ 建议行动:
{chr(10).join("  " + str(i+1) + ". " + r for i, r in enumerate(report.recommendations))}

━ 对标信息:
行业位置: {report.industry_position or "未知"}
信心度: {report.confidence_score*100:.0f}%
"""

    def get_score_explanation(self, report: ESGScoreReport) -> str:
        """生成易读的评分解释。"""
        strengths = chr(10).join("  - " + s for s in report.key_strengths) or "  - No standout strengths captured."
        weaknesses = chr(10).join("  - " + w for w in report.key_weaknesses) or "  - No explicit weaknesses captured."
        recommendations = chr(10).join("  " + str(i + 1) + ". " + r for i, r in enumerate(report.recommendations)) or "  1. No recommendation generated."
        return f"""
ESG 评分报告 - {report.company_name}
{'=' * 50}

综合评分: {report.overall_score:.1f}/100 ({self._get_rating_text(report.overall_score)})
趋势: {report.overall_trend}
JHJ House Score: {report.house_score:.1f}/100 ({report.house_grade}) [{report.formula_version}]
披露可信度: {report.disclosure_confidence * 100:.0f}% · 实质性修正 {report.materiality_adjustment:+.1f}
趋势奖励 {report.trend_bonus:+.1f} · 争议惩罚 {report.controversy_penalty:+.1f} · 数据缺口 {report.data_gap_penalty:+.1f}

━ 环境维度 (E): {report.e_scores.overall_score:.1f}/100
{report.e_scores.summary}

━ 社会维度 (S): {report.s_scores.overall_score:.1f}/100
{report.s_scores.summary}

━ 治理维度 (G): {report.g_scores.overall_score:.1f}/100
{report.g_scores.summary}

━ 核心优势:
{strengths}

━ 主要改进方向:
{weaknesses}

━ 建议行动:
{recommendations}

━ 对标信息:
行业位置: {report.industry_position or "未知"}
信心度: {report.confidence_score * 100:.0f}%

House 解释:
{report.house_explanation}
"""

    @staticmethod
    def _get_rating_text(score: float) -> str:
        """根据分数获取评级文本"""
        if score >= 80:
            return "优秀 ⭐⭐⭐⭐⭐"
        elif score >= 60:
            return "良好 ⭐⭐⭐⭐"
        elif score >= 40:
            return "一般 ⭐⭐⭐"
        elif score >= 20:
            return "需要改进 ⭐⭐"
        else:
            return "不足 ⭐"
