# risk_scorer.py — 风险评分模块
# 职责：使用 LLM 对提取的 ESG 事件进行深度风险评分
# 输出：风险等级 + 分数 + 理由 + 建议

import json
from datetime import datetime, timezone

from gateway.utils.llm_client import chat
from gateway.utils.logger import get_logger
from gateway.models.schemas import RiskScore, RiskLevel
from gateway.db.supabase_client import get_client

logger = get_logger(__name__)
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
IMPACT_AREA_TO_DIMENSION = {
    "e": "environmental",
    "environment": "environmental",
    "environmental": "environmental",
    "s": "social",
    "social": "social",
    "g": "governance",
    "governance": "governance",
}


# ── Risk Scoring Prompt ────────────────────────────────────────────────────

RISK_SCORER_SYSTEM = """You are an ESG risk assessment expert.
Analyze ESG events and score their risk impact on the company and stakeholders.

Return a JSON object with this exact structure:
{
  "risk_level": "<'low' | 'medium' | 'high' | 'critical'>",
  "score": <0-100, where 0=no risk, 100=catastrophic risk>,
  "reasoning": "<2-3 sentences explaining the risk score>",
  "affected_dimensions": {
    "environmental": <0-100>,
    "social": <0-100>,
    "governance": <0-100>
  },
  "recommendation": "<specific action recommendation for stakeholders>"
}

Consider:
1. Business impact magnitude
2. Regulatory/legal implications
3. Shareholder/stakeholder sentiment
4. Industry comparisons
5. Time sensitivity

Only return valid JSON."""

RISK_SCORER_USER = """Event title: {title}
Description: {description}
Event type: {event_type}
Key metrics: {key_metrics}
Impact area: {impact_area}
Current severity: {severity}

Provide a comprehensive risk score."""


class RiskScorer:
    """ESG 事件风险评分器"""

    def __init__(self):
        self.db = get_client()
        self.max_retries = 2

    def _parse_score_json(self, raw: str) -> dict | None:
        """解析 LLM 的 JSON 输出，容错处理 markdown 代码块"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _parse_key_metrics(value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"raw_key_metrics": value}
        return {}

    @staticmethod
    def _severity_floor(base_level: str, candidate_level: str | None, probability: float | None) -> str:
        normalized_base = str(base_level or "low").lower()
        normalized_candidate = str(candidate_level or "").lower()
        if normalized_candidate not in SEVERITY_ORDER:
            return normalized_base
        if float(probability or 0.0) >= 0.55 and SEVERITY_ORDER[normalized_candidate] >= SEVERITY_ORDER.get(normalized_base, 0):
            return normalized_candidate
        return normalized_base

    @staticmethod
    def _dominant_dimension(value: str | None) -> str | None:
        return IMPACT_AREA_TO_DIMENSION.get(str(value or "").strip().lower())

    def score_event(self, event_id: str, event_data: dict) -> dict | None:
        """
        对一个事件进行风险评分。

        Args:
            event_id: 事件 ID
            event_data: 事件数据 {
                "title": "...",
                "description": "...",
                "event_type": "...",
                "key_metrics": {...},
                "impact_area": "E/S/G",
                "severity": "low/medium/high/critical"
            }

        Returns:
            风险评分结果，失败返回 None
        """
        key_metrics = self._parse_key_metrics(event_data.get("key_metrics", {}))
        messages = [
            {"role": "system", "content": RISK_SCORER_SYSTEM},
            {"role": "user", "content": RISK_SCORER_USER.format(
                title=event_data.get("title", ""),
                description=event_data.get("description", ""),
                event_type=event_data.get("event_type", ""),
                key_metrics=json.dumps(key_metrics, ensure_ascii=False),
                impact_area=event_data.get("impact_area", ""),
                severity=event_data.get("severity", ""),
            )},
        ]

        score_data = None

        # 重试循环
        for attempt in range(1, self.max_retries + 2):
            try:
                raw = chat(messages, temperature=0.1, max_tokens=600)
                score_data = self._parse_score_json(raw)
                if score_data:
                    break
                logger.warning(f"[RiskScorer] JSON parse failed (attempt {attempt}), retrying...")
            except Exception as e:
                logger.error(f"[RiskScorer] LLM call failed (attempt {attempt}): {e}")

        if not score_data:
            logger.error(f"[RiskScorer] Failed to score event {event_id}")
            return None

        # 构建评分结果
        try:
            classifier_level = self._severity_floor(
                event_data.get("severity", "low"),
                key_metrics.get("severity_label") or key_metrics.get("controversy_label"),
                key_metrics.get("severity_probability") or key_metrics.get("controversy_probability"),
            )
            calibrated_score = float(score_data.get("score", 50))
            controversy_probability = float(key_metrics.get("controversy_probability", 0.0) or 0.0)
            controversy_level = str(key_metrics.get("controversy_label", "")).lower()
            severity_probability = float(key_metrics.get("severity_probability", 0.0) or 0.0)
            severity_level = str(key_metrics.get("severity_label", "")).lower()
            event_type_probability = float(key_metrics.get("event_type_probability", 0.0) or 0.0)
            impact_area_probability = float(key_metrics.get("impact_area_probability", 0.0) or 0.0)
            if controversy_level in SEVERITY_ORDER:
                uplift_map = {"low": 0.0, "medium": 5.0, "high": 12.0, "critical": 20.0}
                calibrated_score += uplift_map.get(controversy_level, 0.0) * max(0.5, controversy_probability)
                calibrated_score = min(100.0, calibrated_score)
            if severity_level in SEVERITY_ORDER:
                uplift_map = {"low": 0.0, "medium": 4.0, "high": 9.0, "critical": 16.0}
                calibrated_score += uplift_map.get(severity_level, 0.0) * max(0.4, severity_probability)
                calibrated_score = min(100.0, calibrated_score)
            calibrated_level = self._severity_floor(
                score_data.get("risk_level", "medium"),
                classifier_level,
                max(controversy_probability, severity_probability),
            )
            affected_dimensions = score_data.get("affected_dimensions", {
                "environmental": 0, "social": 0, "governance": 0
            })
            dominant_dimension = self._dominant_dimension(
                key_metrics.get("impact_area_label") or event_data.get("impact_area")
            )
            if dominant_dimension and impact_area_probability >= 0.5:
                try:
                    affected_dimensions[dominant_dimension] = max(
                        float(affected_dimensions.get(dominant_dimension, 0.0)),
                        round(55 + impact_area_probability * 35, 2),
                    )
                except Exception:
                    pass
            reasoning = str(score_data.get("reasoning", ""))
            if controversy_level in SEVERITY_ORDER:
                reasoning = (
                    f"{reasoning} Controversy classifier tagged this event as {controversy_level}"
                    f" with probability {controversy_probability:.2f}, which was blended into the final risk calibration."
                ).strip()
            if severity_level in SEVERITY_ORDER:
                reasoning = (
                    f"{reasoning} Severity classifier predicted {severity_level}"
                    f" with probability {severity_probability:.2f}."
                ).strip()
            if key_metrics.get("event_type_label"):
                reasoning = (
                    f"{reasoning} Event-type classifier suggested {key_metrics.get('event_type_label')}"
                    f" ({event_type_probability:.2f}) for downstream routing."
                ).strip()
            score_result = {
                "event_id": event_id,
                "risk_level": calibrated_level,
                "score": calibrated_score,
                "reasoning": reasoning,
                "affected_dimensions": affected_dimensions,
                "recommendation": score_data.get("recommendation", ""),
                "created_at": datetime.now(timezone.utc),
            }

            logger.info(
                f"[RiskScorer] Scored event {event_id}: "
                f"{score_result['risk_level']} ({score_result['score']})"
            )
            return score_result

        except Exception as e:
            logger.error(f"[RiskScorer] Failed to construct score object: {e}")
            return None

    def save_scores(self, scores: list[dict]) -> list[str]:
        """
        保存风险评分到数据库。

        Args:
            scores: 评分结果列表

        Returns:
            保存的评分 ID 列表
        """
        if not scores:
            return []

        saved_ids = []
        try:
            for score in scores:
                result = self.db.table("risk_scores").insert({
                    "event_id": score["event_id"],
                    "risk_level": score["risk_level"],
                    "score": score["score"],
                    "reasoning": score["reasoning"],
                    "affected_dimensions": json.dumps(score["affected_dimensions"], ensure_ascii=False),
                    "recommendation": score["recommendation"],
                    "created_at": score["created_at"].isoformat(),
                }).execute()

                if result.data:
                    saved_ids.append(result.data[0]["id"])

            logger.info(f"[RiskScorer] Saved {len(saved_ids)} scores to database.")
        except Exception as e:
            logger.error(f"[RiskScorer] Failed to save scores: {e}")

        return saved_ids

    def score_batch_events(self, event_ids: list[str]) -> dict:
        """
        批量评分多个事件。

        Args:
            event_ids: 事件 ID 列表

        Returns:
            批量评分结果统计
        """
        if not event_ids:
            return {"total_events": 0, "scored": 0, "saved": 0}

        try:
            # 从数据库读取事件
            response = self.db.table("extracted_events").select("*").in_("id", event_ids).execute()
            events = response.data

            # 评分每个事件
            scores = []
            for event in events:
                score_result = self.score_event(event["id"], event)
                if score_result:
                    scores.append(score_result)

            # 保存评分
            saved_ids = self.save_scores(scores)

            result = {
                "total_events": len(event_ids),
                "scored": len(scores),
                "saved": len(saved_ids),
                "saved_ids": saved_ids,
            }

            logger.info(f"[RiskScorer] Batch scoring complete: {result}")
            return result

        except Exception as e:
            logger.error(f"[RiskScorer] Batch scoring failed: {e}")
            return {"total_events": len(event_ids), "scored": 0, "saved": 0, "error": str(e)}

    def get_top_risks(self, limit: int = 10) -> list[dict]:
        """
        获取最高风险事件。

        Args:
            limit: 返回数量

        Returns:
            风险分数最高的事件列表
        """
        try:
            response = self.db.table("risk_scores").select(
                "*, extracted_events(title, description, company)"
            ).order("score", desc=True).limit(limit).execute()

            logger.info(f"[RiskScorer] Retrieved top {limit} risks")
            return response.data

        except Exception as e:
            logger.error(f"[RiskScorer] Failed to get top risks: {e}")
            return []

    def get_risks_by_level(self, level: str, limit: int = 20) -> list[dict]:
        """
        获取特定风险等级的事件。

        Args:
            level: 风险等级 ("low", "medium", "high", "critical")
            limit: 返回数量

        Returns:
            符合条件的事件列表
        """
        try:
            response = self.db.table("risk_scores").select(
                "*, extracted_events(title, description, company)"
            ).eq("risk_level", level).order("score", desc=True).limit(limit).execute()

            logger.info(f"[RiskScorer] Retrieved {len(response.data)} {level}-risk events")
            return response.data

        except Exception as e:
            logger.error(f"[RiskScorer] Failed to get risks by level: {e}")
            return []


# ── 全局单例 ──────────────────────────────────────────────────────────────

_scorer = None

def get_risk_scorer() -> RiskScorer:
    """获取风险评分器实例（单例）"""
    global _scorer
    if _scorer is None:
        _scorer = RiskScorer()
    return _scorer
