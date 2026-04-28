from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DataProvenance:
    market_data_source: str = "unknown"
    source_chain: tuple[str, ...] = ()
    synthetic_used: bool = False
    synthetic_reason: str = ""
    evidence_eligible: bool = True

    def model_dump(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_chain"] = list(self.source_chain)
        return payload


class SyntheticEvidenceGuard:
    def __init__(self, policy: str = "block") -> None:
        self.policy = str(policy or "block").strip().lower()

    def inspect(self, payload: dict[str, Any] | None, *, fallback_source: str = "unknown") -> DataProvenance:
        payload = dict(payload or {})
        source = str(
            payload.get("market_data_source")
            or payload.get("data_source")
            or payload.get("provider")
            or fallback_source
            or "unknown"
        ).strip().lower()
        chain = payload.get("source_chain")
        if not isinstance(chain, list):
            chain = [source] if source else []
        synthetic_reason = ""
        synthetic_used = bool(payload.get("synthetic_used") or payload.get("used_synthetic_fallback"))
        if not synthetic_used and "synthetic" in source:
            synthetic_used = True
            synthetic_reason = "market_data_source"
        if not synthetic_used and self._value_mentions_synthetic(payload):
            synthetic_used = True
            synthetic_reason = "payload_mentions_synthetic"
        if synthetic_used and not synthetic_reason:
            synthetic_reason = str(payload.get("synthetic_reason") or "synthetic_evidence_detected")
        return DataProvenance(
            market_data_source=source or fallback_source,
            source_chain=tuple(str(item).strip().lower() for item in chain if str(item).strip()),
            synthetic_used=synthetic_used,
            synthetic_reason=synthetic_reason,
            evidence_eligible=not synthetic_used,
        )

    def annotate(self, payload: dict[str, Any], *, fallback_source: str = "unknown") -> dict[str, Any]:
        provenance = self.inspect(payload, fallback_source=fallback_source).model_dump()
        next_payload = dict(payload)
        next_payload.update(provenance)
        next_payload["data_provenance"] = provenance
        return next_payload

    def blockers(self, rows: list[dict[str, Any]]) -> list[str]:
        blockers: list[str] = []
        for row in rows:
            provenance = self.inspect(row)
            if provenance.synthetic_used:
                blockers.append(str(row.get("outcome_id") or row.get("report_id") or row.get("id") or "synthetic_evidence"))
        return blockers

    def summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        synthetic_ids = self.blockers(rows)
        return {
            "policy": self.policy,
            "synthetic_count": len(synthetic_ids),
            "synthetic_ids": synthetic_ids[:25],
            "evidence_eligible": not synthetic_ids,
        }

    def _value_mentions_synthetic(self, value: Any) -> bool:
        if isinstance(value, dict):
            return any(self._value_mentions_synthetic(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(self._value_mentions_synthetic(item) for item in value)
        if isinstance(value, str):
            return "synthetic" in value.lower()
        return False
