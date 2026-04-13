# event_extractor.py — ESG 事件提取模块
# 职责：使用 LLM 从原始扫描数据（新闻、报告）中提取结构化事件和关键信息
# 核心：把非结构化文本 → 结构化事件 + 关键指标

import json
from datetime import datetime, timezone
from typing import Optional

from gateway.scheduler.event_classifier_runtime import get_event_classifier_runtime
from gateway.utils.llm_client import chat
from gateway.utils.logger import get_logger
from gateway.models.schemas import ExtractedEvent, ESGEventType, RiskLevel
from gateway.db.supabase_client import get_client

logger = get_logger(__name__)
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
IMPACT_AREA_MAP = {
    "environment": "E",
    "environmental": "E",
    "e": "E",
    "social": "S",
    "s": "S",
    "governance": "G",
    "g": "G",
}


# ── Extraction Prompt ──────────────────────────────────────────────────────

EXTRACTOR_SYSTEM = """You are an ESG event extraction expert.
Analyze raw ESG news/reports and extract structured information.

Return a JSON object with this exact structure:
{
  "title": "<clear, concise event title>",
  "description": "<2-3 sentence summary>",
  "company": "<primary company affected>",
  "event_type": "<one of: emission_reduction, renewable_energy, water_management,
                           safety_incident, diversity_initiative, community_engagement,
                           governance_change, compliance_violation, corruption_allegation, other>",
  "key_metrics": {
    "<metric_name>": "<extracted value or 'N/A'>"
  },
  "impact_area": "<'E' (environmental) | 'S' (social) | 'G' (governance)>",
  "severity": "<'low' | 'medium' | 'high' | 'critical'>",
  "evidence": "<direct quote from source supporting this classification>"
}

Only return valid JSON. Be strict about severity classification."""

EXTRACTOR_USER = """Raw content:
{raw_content}

Source: {source}"""


class EventExtractor:
    """ESG 事件提取器"""

    def __init__(self):
        self.db = get_client()
        self.max_retries = 2
        self.classifier = get_event_classifier_runtime()

    def _parse_extraction_json(self, raw: str) -> dict | None:
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
    def _merge_severity(base: str, classifier_label: str | None, classifier_probability: float | None) -> str:
        normalized_base = str(base or "low").lower()
        normalized_label = str(classifier_label or "").lower()
        if normalized_label not in SEVERITY_ORDER:
            return normalized_base
        probability = float(classifier_probability or 0.0)
        if probability >= 0.55 and SEVERITY_ORDER[normalized_label] >= SEVERITY_ORDER.get(normalized_base, 0):
            return normalized_label
        return normalized_base

    @staticmethod
    def _normalize_impact_area(value: str | None, fallback: str = "E") -> str:
        return IMPACT_AREA_MAP.get(str(value or "").strip().lower(), fallback)

    def extract_event(self, event_id: str, raw_content: str, source: str, company: str) -> Optional[ExtractedEvent]:
        """
        从原始内容中提取结构化事件。

        Args:
            event_id: 原始事件 ID（来自 scanner）
            raw_content: 原始文本内容
            source: 数据源（news_api, reports_api 等）
            company: 相关公司名称

        Returns:
            提取的结构化事件，失败返回 None
        """
        messages = [
            {"role": "system", "content": EXTRACTOR_SYSTEM},
            {"role": "user", "content": EXTRACTOR_USER.format(
                raw_content=raw_content[:2000],  # 限制长度防止超过 token 限制
                source=source
            )},
        ]

        extracted_data = None

        # 重试循环：JSON 解析失败时重试
        for attempt in range(1, self.max_retries + 2):
            try:
                raw = chat(messages, temperature=0.1, max_tokens=800)
                extracted_data = self._parse_extraction_json(raw)
                if extracted_data:
                    break
                logger.warning(f"[Extractor] JSON parse failed (attempt {attempt}), retrying...")
            except Exception as e:
                logger.error(f"[Extractor] LLM call failed (attempt {attempt}): {e}")

        if not extracted_data:
            logger.error(f"[Extractor] Failed to extract event {event_id}")
            return None

        key_metrics = extracted_data.get("key_metrics", {}) or {}
        if not isinstance(key_metrics, dict):
            key_metrics = {"raw_key_metrics": str(key_metrics)}
        classifier_payload = self.classifier.classify(
            "\n".join(
                part
                for part in [
                    str(extracted_data.get("title", "")),
                    str(extracted_data.get("description", "")),
                    str(raw_content or "")[:1200],
                ]
                if part
            )
        )
        classifier_tasks = dict((classifier_payload or {}).get("tasks", {}))
        if classifier_payload:
            key_metrics.update(
                {
                    "controversy_label": classifier_payload["label"],
                    "controversy_probability": classifier_payload["probability"],
                    "controversy_model_name": classifier_payload["model_name"],
                    "controversy_scores": classifier_payload["scores"],
                }
            )
        severity_task = classifier_tasks.get("severity")
        impact_area_task = classifier_tasks.get("impact_area")
        event_type_task = classifier_tasks.get("event_type")
        if severity_task:
            key_metrics.update(
                {
                    "severity_label": severity_task["label"],
                    "severity_probability": severity_task["probability"],
                    "severity_scores": severity_task["scores"],
                }
            )
        if impact_area_task:
            key_metrics.update(
                {
                    "impact_area_label": impact_area_task["label"],
                    "impact_area_probability": impact_area_task["probability"],
                    "impact_area_scores": impact_area_task["scores"],
                }
            )
        if event_type_task:
            key_metrics.update(
                {
                    "event_type_label": event_type_task["label"],
                    "event_type_probability": event_type_task["probability"],
                    "event_type_scores": event_type_task["scores"],
                }
            )
        severity = self._merge_severity(
            extracted_data.get("severity", "low"),
            (severity_task or {}).get("label") or key_metrics.get("controversy_label"),
            (severity_task or {}).get("probability") or key_metrics.get("controversy_probability"),
        )
        impact_area = self._normalize_impact_area(
            (impact_area_task or {}).get("label"),
            fallback=self._normalize_impact_area(extracted_data.get("impact_area", "E")),
        )
        event_type = str(extracted_data.get("event_type", "other") or "other")
        if event_type_task and float(event_type_task.get("probability") or 0.0) >= 0.52:
            event_type = str(event_type_task.get("label") or event_type)

        # 构建结构化事件对象
        try:
            extracted_event = ExtractedEvent(
                original_event_id=event_id,
                title=extracted_data.get("title", ""),
                description=extracted_data.get("description", ""),
                company=company,
                event_type=event_type,
                key_metrics=key_metrics,
                impact_area=impact_area,
                severity=severity,
                created_at=datetime.now(timezone.utc),
            )

            logger.info(
                f"[Extractor] Extracted event: {extracted_event.title[:60]} "
                f"({extracted_event.event_type}, {extracted_event.severity})"
            )
            return extracted_event

        except Exception as e:
            logger.error(f"[Extractor] Failed to construct event object: {e}")
            return None

    def extract_batch(self, events: list[dict]) -> list[ExtractedEvent]:
        """
        批量提取事件。

        Args:
            events: 格式为 [{"id": "...", "raw_content": "...", "source": "...", "company": "..."}]

        Returns:
            提取成功的事件列表
        """
        extracted = []
        for event in events:
            extracted_event = self.extract_event(
                event_id=event["id"],
                raw_content=event["raw_content"],
                source=event["source"],
                company=event["company"],
            )
            if extracted_event:
                extracted.append(extracted_event)

        logger.info(f"[Extractor] Batch extraction: {len(extracted)}/{len(events)} succeeded")
        return extracted

    def save_extracted_events(self, events: list[ExtractedEvent]) -> list[str]:
        """
        保存提取的结构化事件到数据库。

        Args:
            events: 提取的事件列表

        Returns:
            保存的事件 ID 列表
        """
        if not events:
            return []

        saved_ids = []
        try:
            for event in events:
                result = self.db.table("extracted_events").insert({
                    "original_event_id": event.original_event_id,
                    "title": event.title,
                    "description": event.description,
                    "company": event.company,
                    "event_type": event.event_type,
                    "key_metrics": json.dumps(event.key_metrics, ensure_ascii=False),
                    "impact_area": event.impact_area,
                    "severity": event.severity,
                    "created_at": event.created_at.isoformat(),
                }).execute()

                if result.data:
                    saved_ids.append(result.data[0]["id"])

            logger.info(f"[Extractor] Saved {len(saved_ids)} extracted events to database.")
        except Exception as e:
            logger.error(f"[Extractor] Failed to save extracted events: {e}")

        return saved_ids

    def process_new_events(self, event_ids: list[str]) -> dict:
        """
        处理新扫描的事件：从原始事件表读取，提取结构化信息，保存到提取表。

        Args:
            event_ids: 需要处理的事件 ID 列表

        Returns:
            处理结果统计
        """
        if not event_ids:
            return {"total": 0, "extracted": 0, "saved": 0}

        try:
            # 从数据库读取原始事件
            response = self.db.table("esg_events").select("*").in_("id", event_ids).execute()
            raw_events = response.data

            # 转换为提取器需要的格式
            events_to_extract = [
                {
                    "id": e["id"],
                    "raw_content": e["raw_content"],
                    "source": e["source"],
                    "company": e["company"],
                }
                for e in raw_events
            ]

            # 执行提取
            extracted_events = self.extract_batch(events_to_extract)

            # 保存到数据库
            saved_ids = self.save_extracted_events(extracted_events)

            result = {
                "total": len(raw_events),
                "extracted": len(extracted_events),
                "saved": len(saved_ids),
                "saved_ids": saved_ids,
            }

            logger.info(f"[Extractor] Processing complete: {result}")
            return result

        except Exception as e:
            logger.error(f"[Extractor] Processing failed: {e}")
            return {"total": 0, "extracted": 0, "saved": 0, "error": str(e)}


# ── 全局单例 ──────────────────────────────────────────────────────────────

_extractor = None

def get_extractor() -> EventExtractor:
    """获取事件提取器实例（单例）"""
    global _extractor
    if _extractor is None:
        _extractor = EventExtractor()
    return _extractor
