# esg_scorer.py — ESG 结构化评分框架
# 职责：基于检索到的 ESG 数据，生成结构化的 E/S/G 15维度评分
# 包含：碳排放、能源效率、水资源、废物、可再生能源（E）
#      员工满意度、多样性、供应链伦理、社区关系、客户保护（S）
#      董事会多样性、高管薪酬、反腐机制、风险管理、股东权益（G）

import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from gateway.utils.llm_client import chat
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

    def score_esg(self, company_name: str, esg_data: Dict[str, Any],
                  peers: Optional[List[str]] = None,
                  include_history: bool = False) -> ESGScoreReport:
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

        try:
            # 准备用于LLM的数据摘要
            data_summary = self._prepare_data_summary(company_name, esg_data, peers)

            # 调用LLM进行评分
            raw_response = chat(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": data_summary}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            # 解析JSON响应
            scores_data = self._parse_llm_response(raw_response)

            # 构建报告对象
            report = self._build_report(company_name, esg_data, scores_data)

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
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"  {key}:")
                for k, v in value.items():
                    lines.append(f"    - {k}: {v}")
            else:
                lines.append(f"  - {key}: {value}")
        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON"""
        try:
            # 去掉markdown代码块
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"[ESGScorer] JSON parse error: {e}")
            raise ValueError(f"Failed to parse LLM response: {response[:200]}")

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
            historical_data=esg_data.get("historical_data")
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
