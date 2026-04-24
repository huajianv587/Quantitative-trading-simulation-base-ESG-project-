from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from analysis.technical.market_microstructure import analyze_payload as analyze_market_microstructure
from gateway.connectors.free_live import FreeLiveConnectorRegistry
from gateway.quant.market_depth import MarketDepthGateway
from gateway.quant.intelligence_models import (
    DatasetManifest,
    DecisionReport,
    EvidenceBundle,
    FactorCard,
    FactorCandidate,
    InformationItem,
    InstrumentContract,
    OutcomeRecord,
    ResearchProtectionReport,
    SimulationResult,
    SimulationScenario,
    StructuredEvent,
    SweepRun,
    TearsheetReport,
)
from gateway.quant.models import ResearchSignal, UniverseMember


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _mean(values: list[float], fallback: float = 0.0) -> float:
    return statistics.mean(values) if values else fallback


def _corr(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_den = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_den = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_den <= 0 or right_den <= 0:
        return 0.0
    return _bounded(numerator / (left_den * right_den), -1.0, 1.0)


def _rank(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    for rank, (_, index) in enumerate(ordered, start=1):
        ranks[index] = float(rank)
    return ranks


class QuantIntelligenceService:
    """Evidence, factor research, simulation, and explainable decision layer."""

    def __init__(self, quant_service: Any, data_source_manager: Any | None = None) -> None:
        self.quant_service = quant_service
        self.data_source_manager = data_source_manager
        self.repo_root = Path(__file__).resolve().parents[2]
        self.storage_root = self.repo_root / "storage"
        self._market_depth_service: MarketDepthGateway | None = None

    def _market_depth_gateway(self) -> MarketDepthGateway:
        if (
            self._market_depth_service is None
            or self._market_depth_service.storage_root != Path(self.storage_root)
        ):
            self._market_depth_service = MarketDepthGateway(
                storage_root=Path(self.storage_root),
                market_data=getattr(self.quant_service, "market_data", None),
            )
        return self._market_depth_service

    def market_depth_status(self, *, symbols: list[str] | None = None, require_l2: bool = False) -> dict[str, Any]:
        return self._market_depth_gateway().status(symbols=symbols, require_l2=require_l2)

    def market_depth_latest(self, *, symbol: str) -> dict[str, Any]:
        return self._market_depth_gateway().latest(symbol)

    def market_depth_replay(
        self,
        *,
        symbol: str,
        limit: int = 20,
        timestamps: list[str] | None = None,
        require_l2: bool = False,
        persist: bool = True,
    ) -> dict[str, Any]:
        return self._market_depth_gateway().replay(
            symbol,
            limit=limit,
            timestamps=timestamps,
            require_l2=require_l2,
            persist=persist,
        )

    def get_market_depth_replay(self, session_id: str) -> dict[str, Any] | None:
        return self._market_depth_gateway().load_replay(session_id)

    def market_depth_live_payload(self, *, symbols: list[str] | None = None, require_l2: bool = False) -> dict[str, Any]:
        return self._market_depth_gateway().live_payload(symbols=symbols, require_l2=require_l2)

    def scan(
        self,
        *,
        universe_symbols: list[str] | None = None,
        query: str = "",
        decision_time: str | None = None,
        live_connectors: bool = False,
        mode: str = "local",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        limit: int = 20,
        persist: bool = True,
    ) -> dict[str, Any]:
        decision_time = decision_time or _iso_now()
        mode = str(mode or "local").lower().strip()
        live_enabled = live_connectors or mode in {"live", "mixed"}
        universe = self.quant_service.get_default_universe(universe_symbols)
        signals = self._build_signals(universe, query)
        signal_lookup = {signal.symbol.upper(): signal for signal in signals}
        connector_status = self._connector_status(providers=providers)
        connector_failures: list[str] = []
        items: list[InformationItem] = []

        for member in universe[: max(1, int(limit))]:
            signal = signal_lookup.get(member.symbol.upper())
            if signal is not None and mode != "live":
                items.extend(self._signal_items(member, signal, decision_time))
            if mode != "live":
                items.extend(self._local_esg_items(member, decision_time))
            if live_enabled:
                try:
                    items.extend(self._live_connector_items(member, decision_time, providers=providers, quota_guard=quota_guard))
                except Exception as exc:
                    connector_failures.append(f"{member.symbol}: {exc}")

        items = self._dedup_items(items)
        bundle = EvidenceBundle(
            bundle_id=f"evidence-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{_stable_hash([item.item_id for item in items])[:8]}",
            generated_at=_iso_now(),
            decision_time=decision_time,
            universe=[member.symbol for member in universe],
            query=query,
            items=items,
            connector_status=connector_status
            | {
                "live_connectors_enabled": live_enabled,
                "requested_mode": mode,
                "requested_providers": providers or [],
                "quota_guard": quota_guard,
                "connector_failures": connector_failures,
                "failure_isolation": "enabled",
            },
            quality_summary=self._quality_summary(items),
            lineage=[
                "L0: quant signal engine, local ESG report inventory, optional external connectors",
                "L1: normalized InformationItem schema with checksum, dedup id, and leakage guard",
                "L2: evidence bundle available for factor lab, simulator, and decision reports",
            ],
        )
        payload = bundle.model_dump(mode="json")
        if persist:
            payload["storage"] = self._persist("intelligence/evidence_lake", bundle.bundle_id, payload)
        return payload

    def list_evidence(self, *, symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
        bundles = self._list_json("intelligence/evidence_lake", limit=limit)
        items: list[dict[str, Any]] = []
        symbol_key = str(symbol or "").upper().strip()
        for bundle in bundles:
            for item in bundle.get("items", []):
                if symbol_key and str(item.get("symbol", "")).upper() != symbol_key:
                    continue
                items.append(item)
        if not items and symbol_key:
            fresh = self.scan(universe_symbols=[symbol_key], query="fresh evidence lookup", persist=False)
            items = fresh.get("items", [])
            bundles = [fresh]
        return {
            "generated_at": _iso_now(),
            "symbol": symbol_key or None,
            "bundle_count": len(bundles),
            "items": items[: max(1, int(limit))],
        }

    def extract_events(self, evidence_payload: dict[str, Any] | EvidenceBundle) -> list[StructuredEvent]:
        bundle = evidence_payload if isinstance(evidence_payload, EvidenceBundle) else EvidenceBundle.model_validate(evidence_payload)
        seen: dict[str, int] = {}
        events: list[StructuredEvent] = []
        for item in bundle.items:
            key = f"{item.symbol}:{item.item_type}:{item.title.lower()[:48]}"
            seen[key] = seen.get(key, 0) + 1
            event_type, axis, sentiment, severity = self._infer_event_shape(item)
            direction = "positive" if sentiment > 0.12 else "negative" if sentiment < -0.12 else "neutral"
            novelty = _bounded(1.0 / seen[key])
            events.append(
                StructuredEvent(
                    event_id=f"event-{item.content_hash[:16]}",
                    item_id=item.item_id,
                    symbol=item.symbol,
                    company_name=item.company_name,
                    event_type=event_type,
                    esg_axis=axis,
                    sentiment=round(sentiment, 4),
                    controversy_severity=round(severity, 4),
                    impact_direction=direction,
                    impact_strength=round(_bounded(abs(sentiment) * 0.65 + severity * 0.35), 4),
                    evidence_strength=round(item.quality_score, 4),
                    novelty_score=round(novelty, 4),
                    decay_half_life_days=self._decay_half_life(item, severity),
                    observed_at=item.observed_at,
                    leakage_guard=item.leakage_guard,
                    metadata={"source": item.source, "provider": item.provider, "dedup_id": item.dedup_id},
                )
            )
        return events

    def discover_factors(
        self,
        *,
        universe_symbols: list[str] | None = None,
        query: str = "",
        horizon_days: int = 20,
        decision_time: str | None = None,
        evidence_run_id: str | None = None,
        as_of_time: str | None = None,
        mode: str = "local",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        required_data_tier: str = "l1",
        persist: bool = True,
    ) -> dict[str, Any]:
        loaded_evidence = self._load_evidence(evidence_run_id)
        evidence = loaded_evidence or self.scan(
            universe_symbols=universe_symbols,
            query=query or "discover evidence-linked quant factors",
            decision_time=as_of_time or decision_time,
            live_connectors=str(mode or "").lower() in {"live", "mixed"},
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
            persist=False,
        )
        bundle = EvidenceBundle.model_validate(evidence)
        events = self.extract_events(bundle)
        features = self.build_as_of_features(bundle, events, decision_time=bundle.decision_time)
        dataset_manifest = self._dataset_manifest_from_bundle(
            bundle,
            events,
            features,
            frequency="hybrid" if str(mode or "").lower() in {"live", "mixed"} else "daily",
            required_data_tier=required_data_tier,
            metadata={
                "query": query,
                "source_mode": mode,
                "provider_request": providers or [],
                "include_intraday": str(mode or "").lower() in {"live", "mixed"},
            },
        )
        protection_report = self._protection_report_from_bundle(
            bundle,
            dataset_manifest=dataset_manifest,
            formulas=["avg_quality", "positive_pressure-negative_pressure", "novelty_confidence_blend"],
            frequency=dataset_manifest.frequency,
            required_data_tier=required_data_tier,
        )
        universe = self.quant_service.get_default_universe(universe_symbols or bundle.universe)
        signals = self._build_signals(universe, query)
        signal_returns = {signal.symbol: float(signal.expected_return or 0.0) for signal in signals}

        candidates = self._build_factor_candidates(bundle, events, features, horizon_days)
        cards = [
            self._score_factor(
                candidate,
                signal_returns,
                dataset_id=dataset_manifest.dataset_id,
                protection_status=protection_report.protection_status,
                frequency=dataset_manifest.frequency,
                data_tier=dataset_manifest.data_tier,
                blocking_reasons=protection_report.blocking_reasons,
            )
            for candidate in candidates
        ]
        payload = {
            "run_id": f"factorlab-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{_stable_hash([card.factor_id for card in cards])[:8]}",
            "generated_at": _iso_now(),
            "decision_time": bundle.decision_time,
            "evidence_run_id": evidence_run_id or bundle.bundle_id,
            "source_mode": mode,
            "connector_lineage": bundle.connector_status,
            "query": query,
            "horizon_days": horizon_days,
            "universe": [member.symbol for member in universe],
            "dataset_manifest": dataset_manifest.model_dump(mode="json"),
            "protection_report": protection_report.model_dump(mode="json"),
            "features": features,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "factor_cards": [card.model_dump(mode="json") for card in cards],
            "promotion_policy": {
                "requires_as_of_safe": True,
                "requires_sample_count": 3,
                "requires_abs_ic": 0.05,
                "transaction_cost_failure_status": "research_only",
                "small_sample_status": "low_confidence",
            },
            "lineage": bundle.lineage
            + [
                "L3: as-of event feature store",
                "L4: factor candidates scored with IC, RankIC, coverage, turnover, and leakage gates",
            ],
        }
        if persist:
            payload["storage"] = self._persist("quant/factor_lab", payload["run_id"], payload)
            self._persist_factor_registry(cards)
        return payload

    def factor_registry(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self._list_json("quant/factor_registry", limit=limit)
        if not rows:
            discovered = self.discover_factors(persist=False)
            rows = discovered.get("factor_cards", [])
        latest_factor_run = self._list_json("quant/factor_lab", limit=1)
        latest_payload = latest_factor_run[0] if latest_factor_run else {}
        return {
            "generated_at": _iso_now(),
            "factor_count": len(rows),
            "factors": rows[: max(1, int(limit))],
            "registry_policy": "Only promoted factors can become runtime inputs; research_only factors remain visible but gated.",
            "latest_dataset_manifest": latest_payload.get("dataset_manifest", {}),
            "latest_protection_report": latest_payload.get("protection_report", {}),
        }

    def build_dataset_manifest(
        self,
        *,
        universe_symbols: list[str] | None = None,
        query: str = "",
        as_of_time: str | None = None,
        decision_time: str | None = None,
        mode: str = "local",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        frequency: str = "daily",
        include_intraday: bool = True,
        required_data_tier: str = "l1",
        persist: bool = True,
    ) -> dict[str, Any]:
        evidence = self.scan(
            universe_symbols=universe_symbols,
            query=query or "build dataset manifest",
            decision_time=as_of_time or decision_time,
            live_connectors=str(mode or "").lower() in {"live", "mixed"},
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
            persist=False,
        )
        bundle = EvidenceBundle.model_validate(evidence)
        events = self.extract_events(bundle)
        features = self.build_as_of_features(bundle, events, decision_time=bundle.decision_time)
        dataset = self._dataset_manifest_from_bundle(
            bundle,
            events,
            features,
            frequency="hybrid" if include_intraday and frequency in {"daily", "intraday", "hybrid"} else frequency,
            required_data_tier=required_data_tier,
            metadata={
                "query": query,
                "mode": mode,
                "providers": providers or [],
                "include_intraday": include_intraday,
                "event_count": len(events),
            },
        )
        payload = dataset.model_dump(mode="json")
        if persist:
            payload["storage"] = self._persist("quant/research_datasets", dataset.dataset_id, payload)
        return payload

    def list_dataset_manifests(self, *, limit: int = 20) -> dict[str, Any]:
        rows = self._list_json("quant/research_datasets", limit=limit)
        return {
            "generated_at": _iso_now(),
            "dataset_count": len(rows),
            "datasets": rows,
        }

    def run_research_quality_checks(
        self,
        *,
        universe_symbols: list[str] | None = None,
        query: str = "",
        decision_time: str | None = None,
        as_of_time: str | None = None,
        evidence_run_id: str | None = None,
        mode: str = "local",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        frequency: str = "daily",
        formulas: list[str] | None = None,
        labels: list[dict[str, Any]] | None = None,
        timestamps: list[str] | None = None,
        current_constituents_only: bool = False,
        required_data_tier: str = "l1",
        persist: bool = True,
    ) -> dict[str, Any]:
        evidence_payload = self._load_evidence(evidence_run_id)
        if evidence_payload is None:
            evidence_payload = self.scan(
                universe_symbols=universe_symbols,
                query=query or "quality checks",
                decision_time=as_of_time or decision_time,
                live_connectors=str(mode or "").lower() in {"live", "mixed"},
                mode=mode,
                providers=providers,
                quota_guard=quota_guard,
                persist=False,
            )
        bundle = EvidenceBundle.model_validate(evidence_payload)
        events = self.extract_events(bundle)
        features = self.build_as_of_features(bundle, events, decision_time=bundle.decision_time)
        dataset = self._dataset_manifest_from_bundle(
            bundle,
            events,
            features,
            frequency=frequency,
            required_data_tier=required_data_tier,
            metadata={"query": query, "mode": mode, "providers": providers or []},
        )
        report = self._protection_report_from_bundle(
            bundle,
            dataset_manifest=dataset,
            formulas=formulas or [],
            labels=labels or [],
            timestamps=timestamps or [],
            current_constituents_only=current_constituents_only,
            frequency=frequency,
            required_data_tier=required_data_tier,
        )
        payload = report.model_dump(mode="json")
        if persist:
            payload["storage"] = self._persist("quant/research_quality", report.report_id, payload)
        return payload

    def explain_decision(
        self,
        *,
        symbol: str = "AAPL",
        universe_symbols: list[str] | None = None,
        query: str = "",
        horizon_days: int = 20,
        include_simulation: bool = True,
        evidence_run_id: str | None = None,
        mode: str = "local",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        universe_symbols = universe_symbols or [symbol]
        universe = self.quant_service.get_default_universe(universe_symbols)
        signals = self._build_signals(universe, query or f"Explain decision for {symbol}")
        signal = self._select_signal(signals, symbol)
        if signal is None:
            raise ValueError(f"No signal available for {symbol}")

        evidence_payload = self._load_evidence(evidence_run_id) or self.scan(
            universe_symbols=[signal.symbol],
            query=query,
            persist=False,
            mode=mode,
            live_connectors=str(mode or "").lower() in {"live", "mixed"},
            providers=providers,
            quota_guard=quota_guard,
        )
        evidence = EvidenceBundle.model_validate(evidence_payload)
        events = self.extract_events(evidence)
        factor_payload = self.discover_factors(
            universe_symbols=[signal.symbol],
            query=query,
            horizon_days=horizon_days,
            decision_time=evidence.decision_time,
            evidence_run_id=evidence_run_id or evidence.bundle_id,
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
            persist=False,
        )
        cards = [FactorCard.model_validate(item) for item in factor_payload.get("factor_cards", [])]
        simulation_payload = None
        if include_simulation:
            simulation_payload = self.simulate_scenario(
                SimulationScenario(
                    symbol=signal.symbol,
                    universe=[signal.symbol],
                    horizon_days=horizon_days,
                    shock_bps=0.0,
                    scenario_name="decision_base_case",
                    event_assumption=query or "base evidence bundle",
                ),
                signal_override=signal,
                evidence_override=evidence,
                persist=False,
            )
        simulation = SimulationResult.model_validate(simulation_payload) if simulation_payload else None
        main_evidence, counter_evidence = self._split_evidence(signal, evidence.items, events)
        confidence_interval = self._confidence_interval(signal, simulation)
        report = DecisionReport(
            decision_id=f"decision-{signal.symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            generated_at=_iso_now(),
            decision_time=evidence.decision_time,
            symbol=signal.symbol,
            company_name=signal.company_name,
            action=signal.action,
            position_weight_range=self._position_range(signal),
            confidence=round(float(signal.decision_confidence or signal.confidence or 0.0), 4),
            confidence_interval=confidence_interval,
            expected_return=round(float(signal.expected_return or 0.0), 6),
            main_evidence=main_evidence[:5],
            counter_evidence=counter_evidence[:5],
            risk_triggers=self._risk_triggers(signal, events),
            factor_attribution=self._factor_attribution(signal, cards),
            factor_cards=cards[:6],
            simulation=simulation,
            verifier_checks=self._verify_decision(evidence, signal, main_evidence, counter_evidence),
            data_versions={
                "evidence_bundle_id": evidence.bundle_id,
                "factor_lab_run_id": factor_payload.get("run_id"),
                "storage_contract": "source-linked, timestamped, checksumed, as-of guarded",
            },
            model_versions={
                "alpha_model": signal.alpha_model_name or signal.alpha_engine or "heuristic_alpha_stack",
                "p1_model": signal.p1_model_version or "p1_runtime_or_fallback",
                "p2_model": "p2_decision_stack" if signal.decision_score is not None else "p2_unavailable",
                "simulation": "deterministic_shadow_simulator_v1",
            },
            audit_trail=[
                "No broker order is created by this endpoint.",
                "Decision is shadow-mode research support, not live execution.",
                "Verifier checks source presence, timestamp safety, evidence conflict, and confidence bounds.",
            ],
        )
        payload = report.model_dump(mode="json")
        payload["connector_lineage"] = evidence.connector_status
        payload["evidence_conflicts"] = {
            "counter_evidence_count": len(counter_evidence),
            "provider_count": len({item.provider for item in evidence.items}),
            "future_dated_items": sum(1 for item in evidence.items if item.leakage_guard != "as_of_safe"),
        }
        payload["live_data_age"] = self._live_data_age(evidence.items, evidence.decision_time)
        payload["quota_mode"] = evidence.connector_status.get("quota_guard", quota_guard)
        if persist:
            payload["storage"] = self._persist("quant/decision_reports", report.decision_id, payload)
        return payload

    def simulate_scenario(
        self,
        scenario: SimulationScenario | dict[str, Any],
        *,
        signal_override: ResearchSignal | None = None,
        evidence_override: EvidenceBundle | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        scenario = scenario if isinstance(scenario, SimulationScenario) else SimulationScenario.model_validate(scenario)
        universe = self.quant_service.get_default_universe(scenario.universe or [scenario.symbol])
        signals = self._build_signals(universe, scenario.event_assumption or scenario.scenario_name)
        signal = signal_override or self._select_signal(signals, scenario.symbol)
        if signal is None:
            raise ValueError(f"No signal available for {scenario.symbol}")

        evidence_payload = self._load_evidence(scenario.evidence_run_id) if scenario.evidence_run_id else None
        evidence = evidence_override or EvidenceBundle.model_validate(
            evidence_payload or self.scan(universe_symbols=[signal.symbol], query=scenario.event_assumption, persist=False)
        )
        event_adjustment = self._event_adjustment(evidence, scenario.event_id)
        rng = random.Random(int(scenario.seed))
        annual_vol = float(signal.predicted_volatility_10d or 0.22)
        daily_vol = max(annual_vol / math.sqrt(252), 0.003)
        base_return = float(signal.expected_return or 0.0) + float(scenario.shock_bps) / 10000.0 + event_adjustment
        cost = (float(scenario.transaction_cost_bps) + float(scenario.slippage_bps)) / 10000.0
        horizon_scale = math.sqrt(max(1, scenario.horizon_days))
        events = self.extract_events(evidence)
        features = self.build_as_of_features(evidence, events, decision_time=evidence.decision_time)
        dataset_manifest = self._dataset_manifest_from_bundle(
            evidence,
            events,
            features,
            frequency="intraday",
            required_data_tier=scenario.required_data_tier,
            metadata={
                "scenario_name": scenario.scenario_name,
                "regime": scenario.regime,
                "event_assumption": scenario.event_assumption,
            },
        )
        protection_report = self._protection_report_from_bundle(
            evidence,
            dataset_manifest=dataset_manifest,
            formulas=["intraday_replay", "execution_quality", "market_depth_replay"],
            frequency="intraday",
            required_data_tier=scenario.required_data_tier,
        )
        market_depth_status = dataset_manifest.market_depth_status
        results: list[float] = []
        drawdowns: list[float] = []
        for _ in range(int(scenario.paths)):
            shock = rng.gauss(0.0, daily_vol * horizon_scale)
            regime_shift = -0.012 if scenario.regime == "risk_off" else 0.008 if scenario.regime == "risk_on" else 0.0
            path_return = base_return + shock + regime_shift - cost
            results.append(path_return)
            drawdowns.append(max(0.0, -path_return * rng.uniform(0.55, 1.45)))
        results.sort()
        drawdowns.sort()
        p05 = self._quantile(results, 0.05)
        losses = [value for value in results if value < 0.0]
        factor_attr = self._signal_factor_dict(signal)
        result = SimulationResult(
            simulation_id=f"sim-{signal.symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{_stable_hash(scenario.model_dump(mode='json'))[:8]}",
            generated_at=_iso_now(),
            scenario=scenario,
            data_tier=dataset_manifest.data_tier,  # type: ignore[arg-type]
            expected_return=round(_mean(results), 6),
            median_return=round(self._quantile(results, 0.5), 6),
            probability_of_loss=round(len(losses) / max(len(results), 1), 6),
            max_drawdown_p95=round(self._quantile(drawdowns, 0.95), 6),
            value_at_risk_95=round(p05, 6),
            expected_shortfall_95=round(_mean([value for value in results if value <= p05], p05), 6),
            path_summary={
                "p05": round(p05, 6),
                "p25": round(self._quantile(results, 0.25), 6),
                "p50": round(self._quantile(results, 0.50), 6),
                "p75": round(self._quantile(results, 0.75), 6),
                "p95": round(self._quantile(results, 0.95), 6),
            },
            factor_attribution=factor_attr,
            historical_analogs=self._historical_analogs(evidence, scenario),
            market_depth_status=market_depth_status,
            lineage=[
                "L0: current research signal expected return and volatility proxy",
                "L1: deterministic seeded Monte Carlo with transaction cost and slippage",
                "L2: evidence bundle searched for historical analog labels",
                "L3: market depth replay and protection gate aligned to simulation scenario",
            ],
        )
        payload = result.model_dump(mode="json")
        intraday_replay = self._build_intraday_replay(signal, scenario)
        order_book_replay = self.market_depth_replay(
            symbol=signal.symbol,
            limit=min(24, max(8, int(scenario.paths // 32))),
            require_l2=scenario.required_data_tier == "l2",
            persist=persist,
        )
        microstructure = analyze_market_microstructure(
            {
                "symbol": signal.symbol,
                "records": intraday_replay["bars"],
                "order_book_snapshots": order_book_replay.get("snapshots", []),
                "base_spread_bps": float(scenario.slippage_bps or 5.0) + float(scenario.transaction_cost_bps or 8.0) * 0.4,
            }
        )
        payload["intraday_replay"] = intraday_replay
        payload["order_book_replay"] = order_book_replay
        payload["microstructure"] = microstructure
        payload["dataset_manifest"] = dataset_manifest.model_dump(mode="json")
        payload["protection_report"] = protection_report.model_dump(mode="json")
        payload["market_depth_status"] = market_depth_status
        payload["data_tier"] = dataset_manifest.data_tier
        payload["execution_quality_sandbox"] = {
            "best_session": microstructure.get("metrics", {}).get("best_session"),
            "session_breakdown": microstructure.get("session_breakdown", {}),
            "scenarios": microstructure.get("execution_scenarios", []),
            "warnings": microstructure.get("warnings", []),
            "fallback_banner": "Real L2 unavailable; showing explicit L1 proxy diagnostics."
            if order_book_replay.get("data_tier") != "l2"
            else "",
            "l2_source": order_book_replay.get("provider"),
            "registry_gate_status": "blocked" if protection_report.protection_status == "blocked" else "review",
        }
        if persist:
            payload["storage"] = self._persist("quant/simulation_results", result.simulation_id, payload)
        return payload

    def evaluate_outcome(
        self,
        *,
        symbol: str = "AAPL",
        decision_id: str | None = None,
        horizon_days: int = 20,
        realized_return: float | None = None,
        benchmark_return: float = 0.0,
        drawdown: float | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        if realized_return is None:
            records = self._list_json("quant/outcome_tracking", limit=200)
            return self._outcome_summary(records)

        decision = self._load_decision(decision_id) if decision_id else None
        predicted = float(decision.get("expected_return")) if decision and decision.get("expected_return") is not None else None
        excess = float(realized_return) - float(benchmark_return)
        direction_hit = None if predicted is None else (predicted >= 0) == (float(realized_return) >= 0)
        brier = None
        if predicted is not None:
            confidence = float(decision.get("confidence") or 0.5)
            outcome = 1.0 if float(realized_return) > 0 else 0.0
            brier = (confidence - outcome) ** 2
        record = OutcomeRecord(
            outcome_id=f"outcome-{symbol.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            decision_id=decision_id,
            symbol=symbol.upper(),
            recorded_at=_iso_now(),
            decision_time=decision.get("decision_time") if decision else None,
            horizon_days=horizon_days,
            predicted_return=predicted,
            realized_return=round(float(realized_return), 6),
            benchmark_return=round(float(benchmark_return), 6),
            excess_return=round(excess, 6),
            direction_hit=direction_hit,
            brier_component=round(brier, 6) if brier is not None else None,
            regret=round(max(0.0, (predicted or 0.0) - float(realized_return)), 6) if predicted is not None else None,
            drawdown_breach=bool(drawdown is not None and drawdown <= -0.08),
            notes=notes,
            lineage=[
                "L0: shadow-mode decision report",
                "L1: realized return supplied by operator or later market-data job",
                "L2: calibration and regret metrics for future model upgrades",
            ],
        )
        payload = record.model_dump(mode="json")
        payload["storage"] = self._persist("quant/outcome_tracking", record.outcome_id, payload)
        return {"record": payload, "summary": self._outcome_summary(self._list_json("quant/outcome_tracking", limit=200))}

    def build_as_of_features(
        self,
        bundle: EvidenceBundle | dict[str, Any],
        events: list[StructuredEvent],
        *,
        decision_time: str,
    ) -> dict[str, dict[str, float]]:
        bundle = bundle if isinstance(bundle, EvidenceBundle) else EvidenceBundle.model_validate(bundle)
        cutoff = _parse_dt(decision_time) or datetime.now(timezone.utc)
        event_lookup: dict[str, list[StructuredEvent]] = {}
        for event in events:
            observed = _parse_dt(event.observed_at)
            if observed is None or observed > cutoff:
                continue
            event_lookup.setdefault(event.symbol, []).append(event)

        features: dict[str, dict[str, float]] = {}
        for symbol in sorted({item.symbol for item in bundle.items} | set(event_lookup)):
            safe_items = [
                item
                for item in bundle.items
                if item.symbol == symbol and (_parse_dt(item.observed_at) or cutoff) <= cutoff
            ]
            symbol_events = event_lookup.get(symbol, [])
            negative = [event.impact_strength for event in symbol_events if event.impact_direction == "negative"]
            positive = [event.impact_strength for event in symbol_events if event.impact_direction == "positive"]
            features[symbol] = {
                "evidence_count": float(len(safe_items)),
                "event_count": float(len(symbol_events)),
                "avg_quality": round(_mean([item.quality_score for item in safe_items]), 6),
                "avg_confidence": round(_mean([item.confidence for item in safe_items]), 6),
                "negative_pressure": round(_mean(negative), 6),
                "positive_pressure": round(_mean(positive), 6),
                "controversy_severity": round(_mean([event.controversy_severity for event in symbol_events]), 6),
                "novelty": round(_mean([event.novelty_score for event in symbol_events]), 6),
                "as_of_safe_ratio": round(
                    sum(1 for item in safe_items if item.leakage_guard == "as_of_safe") / max(len(safe_items), 1),
                    6,
                ),
            }
        return features

    def audit_trail(self, *, symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
        symbol_key = str(symbol or "").upper().strip()
        rows = self._list_json("quant/decision_reports", limit=limit)
        if symbol_key:
            rows = [row for row in rows if str(row.get("symbol", "")).upper() == symbol_key]
        return {
            "generated_at": _iso_now(),
            "symbol": symbol_key or None,
            "decision_count": len(rows),
            "decisions": rows[: max(1, int(limit))],
        }

    def _build_signals(self, universe: list[UniverseMember], query: str) -> list[ResearchSignal]:
        return self.quant_service._build_signals(universe, query or "intelligence shadow signal", self.quant_service.default_benchmark)

    def _signal_items(self, member: UniverseMember, signal: ResearchSignal, observed_at: str) -> list[InformationItem]:
        items = [
            self._make_item(
                item_type="market_signal",
                provider=signal.market_data_source or signal.signal_source or "quant_engine",
                source="quant_signal_engine",
                symbol=member.symbol,
                company_name=member.company_name,
                title=f"{member.symbol} {signal.action.upper()} research signal",
                summary=signal.thesis,
                observed_at=observed_at,
                confidence=float(signal.decision_confidence or signal.confidence or 0.0),
                metadata={
                    "action": signal.action,
                    "expected_return": signal.expected_return,
                    "risk_score": signal.risk_score,
                    "overall_score": signal.overall_score,
                    "data_lineage": signal.data_lineage,
                },
            )
        ]
        for factor in signal.factor_scores[:6]:
            items.append(
                self._make_item(
                    item_type="model_signal",
                    provider=signal.alpha_model_name or signal.alpha_engine or "factor_runtime",
                    source="research_signal.factor_scores",
                    symbol=member.symbol,
                    company_name=member.company_name,
                    title=f"{member.symbol} factor {factor.name}",
                    summary=f"{factor.description}; value={factor.value:.2f}; contribution={factor.contribution:.2f}",
                    observed_at=observed_at,
                    confidence=_bounded(float(signal.confidence or 0.0) * 0.92),
                    metadata={"factor_name": factor.name, "value": factor.value, "contribution": factor.contribution},
                )
            )
        for catalyst in signal.catalysts[:3]:
            items.append(
                self._make_item(
                    item_type="rag_evidence",
                    provider="quant_signal_catalyst",
                    source="research_signal.catalysts",
                    symbol=member.symbol,
                    company_name=member.company_name,
                    title=f"{member.symbol} catalyst",
                    summary=str(catalyst),
                    observed_at=observed_at,
                    confidence=_bounded(float(signal.confidence or 0.0) * 0.85),
                    metadata={"signal_source": signal.signal_source},
                )
            )
        return items

    def _local_esg_items(self, member: UniverseMember, observed_at: str) -> list[InformationItem]:
        report_dir = self.repo_root / "esg_reports"
        paths = sorted(report_dir.glob(f"**/{member.symbol}_ESG_2025*.pdf"))[:2]
        if member.symbol.upper() == "AAPL":
            paths = sorted((report_dir / "Apple").glob("Apple * 2025*.pdf"))[:2]
        if not paths:
            return []
        items: list[InformationItem] = []
        for path in paths:
            checksum = _stable_hash({"path": str(path.relative_to(self.repo_root)), "size": path.stat().st_size})
            items.append(
                self._make_item(
                    item_type="esg_report",
                    provider="local_esg_corpus",
                    source=str(path.relative_to(self.repo_root)).replace("\\", "/"),
                    symbol=member.symbol,
                    company_name=member.company_name,
                    title=f"{member.symbol} ESG report evidence",
                    summary=f"Local ESG corpus report available for {member.company_name}: {path.name}",
                    observed_at=observed_at,
                    event_date="2025-12-31",
                    confidence=0.88,
                    checksum=checksum,
                    metadata={"file_size": path.stat().st_size, "paper_grade_source": True},
                )
            )
        return items

    def _live_connector_items(
        self,
        member: UniverseMember,
        observed_at: str,
        *,
        providers: list[str] | None = None,
        quota_guard: bool = True,
    ) -> list[InformationItem]:
        manager = self.data_source_manager
        if manager is None:
            registry_items = self._free_connector_items(member, observed_at, providers=providers, quota_guard=quota_guard)
            if registry_items:
                return registry_items
            manager = self._default_data_source_manager()
        if manager is None:
            return []
        company_data = manager.fetch_company_data(member.company_name, ticker=member.symbol, industry=member.industry)
        items: list[InformationItem] = []
        for raw in list(getattr(company_data, "recent_news", []) or [])[:5]:
            title = str(raw.get("title") or raw.get("headline") or f"{member.symbol} external news")
            summary = str(raw.get("description") or raw.get("summary") or raw.get("content") or title)
            items.append(
                self._make_item(
                    item_type="news",
                    provider=str(raw.get("provider") or raw.get("source") or "external_news"),
                    source=str(raw.get("source") or "external_news"),
                    url=raw.get("url"),
                    symbol=member.symbol,
                    company_name=member.company_name,
                    title=title,
                    summary=summary,
                    published_at=raw.get("published_at") or raw.get("publishedAt"),
                    observed_at=observed_at,
                    confidence=0.72,
                    metadata={"connector": "DataSourceManager", "license_note": "external data source terms apply"},
                )
            )
        return items

    def _free_connector_items(
        self,
        member: UniverseMember,
        observed_at: str,
        *,
        providers: list[str] | None = None,
        quota_guard: bool = True,
    ) -> list[InformationItem]:
        registry = self._connector_registry()
        scan = registry.live_scan(
            universe=[member.symbol],
            providers=providers,
            decision_time=observed_at,
            quota_guard=quota_guard,
            persist=False,
        )
        items: list[InformationItem] = []
        for raw in scan.get("items", []):
            item_type = str(raw.get("item_type") or "news")
            if item_type not in {
                "news",
                "filing",
                "esg_report",
                "earnings_call",
                "market_signal",
                "macro",
                "risk_event",
                "rag_evidence",
                "model_signal",
                "connector_status",
            }:
                item_type = "news"
            items.append(
                self._make_item(
                    item_type=item_type,
                    provider=str(raw.get("provider") or "free_live_connector"),
                    source=str(raw.get("source") or raw.get("provider") or "free_live_connector"),
                    url=raw.get("url"),
                    symbol=member.symbol,
                    company_name=member.company_name,
                    title=str(raw.get("title") or f"{member.symbol} live connector evidence"),
                    summary=str(raw.get("summary") or raw.get("title") or ""),
                    published_at=raw.get("published_at"),
                    observed_at=observed_at,
                    confidence=float(raw.get("confidence") or 0.66),
                    checksum=raw.get("checksum"),
                    metadata={
                        "connector": "FreeLiveConnectorRegistry",
                        "free_tier_mode": True,
                        "license_note": raw.get("license_note"),
                        **(raw.get("metadata") or {}),
                    },
                )
            )
        return items

    def _default_data_source_manager(self) -> Any | None:
        try:
            from gateway.scheduler.data_sources import DataSourceManager

            return DataSourceManager()
        except Exception:
            return None

    def _connector_registry(self) -> FreeLiveConnectorRegistry:
        return FreeLiveConnectorRegistry(storage_root=self.storage_root)

    def _connector_status(self, providers: list[str] | None = None) -> dict[str, Any]:
        registry = self._connector_registry()
        free_status = registry.health(providers=providers, live=False)
        manager = self.data_source_manager or self._default_data_source_manager()
        if manager is None:
            return {"available": True, "sources": {}, "mode": "free_tier_registry", "free_tier_registry": free_status}
        try:
            status = manager.source_status()
        except Exception:
            status = {}
        return {"available": True, "sources": status, "mode": "free_tier_registry", "free_tier_registry": free_status}

    def _make_item(
        self,
        *,
        item_type: str,
        provider: str,
        source: str,
        symbol: str,
        company_name: str,
        title: str,
        summary: str,
        observed_at: str,
        confidence: float,
        url: str | None = None,
        published_at: str | None = None,
        event_date: str | None = None,
        checksum: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InformationItem:
        content = {
            "item_type": item_type,
            "provider": provider,
            "source": source,
            "symbol": symbol.upper(),
            "title": title,
            "summary": summary,
            "published_at": published_at,
            "observed_at": observed_at,
            "event_date": event_date,
        }
        content_hash = _stable_hash(content)
        observed = _parse_dt(observed_at)
        published = _parse_dt(published_at or event_date or observed_at)
        if observed is None:
            leakage_guard = "missing_timestamp_warning"
        elif published is not None and published > observed:
            leakage_guard = "future_dated_warning"
        else:
            leakage_guard = "as_of_safe"
        freshness = self._freshness_score(published, observed)
        quality = self._quality_score(
            item_type=item_type,
            provider=provider,
            confidence=confidence,
            freshness=freshness,
            leakage_guard=leakage_guard,
        )
        return InformationItem(
            item_id=f"info-{symbol.upper()}-{content_hash[:16]}",
            item_type=item_type,  # type: ignore[arg-type]
            provider=provider,
            source=source,
            url=url,
            title=title,
            summary=summary,
            symbol=symbol.upper(),
            company_name=company_name,
            published_at=published_at,
            observed_at=observed_at,
            event_date=event_date,
            checksum=checksum or content_hash,
            content_hash=content_hash,
            freshness_score=round(freshness, 6),
            confidence=round(_bounded(confidence), 6),
            quality_score=round(quality, 6),
            dedup_id=f"{symbol.upper()}:{item_type}:{content_hash[:12]}",
            leakage_guard=leakage_guard,  # type: ignore[arg-type]
            metadata=metadata or {},
        )

    def _freshness_score(self, published: datetime | None, observed: datetime | None) -> float:
        if published is None or observed is None:
            return 0.55
        age_days = max((observed - published).total_seconds() / 86400.0, 0.0)
        return _bounded(math.exp(-age_days / 45.0), 0.05, 1.0)

    def _quality_score(self, *, item_type: str, provider: str, confidence: float, freshness: float, leakage_guard: str) -> float:
        source_weights = {
            "esg_report": 0.92,
            "filing": 0.94,
            "market_signal": 0.84,
            "model_signal": 0.78,
            "rag_evidence": 0.74,
            "news": 0.68,
            "macro": 0.72,
            "risk_event": 0.70,
        }
        provider_bonus = 0.05 if any(token in provider.lower() for token in ("sec", "local_esg", "alpaca", "yfinance")) else 0.0
        leakage_penalty = 0.25 if leakage_guard != "as_of_safe" else 0.0
        raw = 0.44 * _bounded(confidence) + 0.34 * (source_weights.get(item_type, 0.65) + provider_bonus) + 0.22 * freshness - leakage_penalty
        return _bounded(raw)

    def _dedup_items(self, items: list[InformationItem]) -> list[InformationItem]:
        best: dict[str, InformationItem] = {}
        for item in items:
            existing = best.get(item.dedup_id)
            if existing is None or item.quality_score > existing.quality_score:
                best[item.dedup_id] = item
        return sorted(best.values(), key=lambda item: (item.symbol, -item.quality_score, item.item_type))

    def _quality_summary(self, items: list[InformationItem]) -> dict[str, Any]:
        return {
            "item_count": len(items),
            "avg_quality": round(_mean([item.quality_score for item in items]), 6),
            "avg_confidence": round(_mean([item.confidence for item in items]), 6),
            "as_of_safe_ratio": round(
                sum(1 for item in items if item.leakage_guard == "as_of_safe") / max(len(items), 1),
                6,
            ),
            "source_types": sorted({item.item_type for item in items}),
            "providers": sorted({item.provider for item in items}),
        }

    def _infer_event_shape(self, item: InformationItem) -> tuple[str, str, float, float]:
        text = f"{item.title} {item.summary}".lower()
        axis = "NONE"
        if any(token in text for token in ("carbon", "emission", "renewable", "climate", "environment")):
            axis = "E"
        elif any(token in text for token in ("labor", "employee", "safety", "community", "privacy", "customer")):
            axis = "S"
        elif any(token in text for token in ("board", "audit", "governance", "shareholder", "compliance")):
            axis = "G"
        elif any(token in text for token in ("esg", "sustainability")):
            axis = "MIXED"

        negative_tokens = ("controversy", "risk", "breach", "penalty", "lawsuit", "weak", "death_cross", "drawdown")
        positive_tokens = ("improve", "strong", "leader", "positive", "golden_cross", "bullish", "above")
        neg = sum(1 for token in negative_tokens if token in text)
        pos = sum(1 for token in positive_tokens if token in text)
        sentiment = _bounded((pos - neg) / 4.0, -1.0, 1.0)
        severity = _bounded((neg * 0.22) + (0.08 if item.item_type == "risk_event" else 0.0))
        if item.item_type == "market_signal":
            event_type = "market_momentum"
        elif item.item_type == "esg_report":
            event_type = "esg_disclosure"
        elif item.item_type == "news":
            event_type = "external_news"
        elif severity > 0:
            event_type = "risk_or_controversy"
        else:
            event_type = "evidence_update"
        return event_type, axis, sentiment, severity

    def _decay_half_life(self, item: InformationItem, severity: float) -> int:
        if item.item_type == "market_signal":
            return 10
        if item.item_type == "news":
            return 7 if severity < 0.25 else 21
        if item.item_type == "esg_report":
            return 180
        return 30

    def _build_factor_candidates(
        self,
        bundle: EvidenceBundle,
        events: list[StructuredEvent],
        features: dict[str, dict[str, float]],
        horizon_days: int,
    ) -> list[FactorCandidate]:
        source_ids = [item.item_id for item in bundle.items]
        safe = all(item.leakage_guard == "as_of_safe" for item in bundle.items)
        candidates = [
            FactorCandidate(
                factor_id=f"factor-evidence-strength-{bundle.bundle_id[-8:]}",
                name="evidence_strength",
                family="evidence_quality",
                description="Average source quality and confidence for each symbol.",
                horizon_days=horizon_days,
                universe=list(features),
                exposures={symbol: values.get("avg_quality", 0.0) * 100.0 for symbol, values in features.items()},
                source_item_ids=source_ids,
                leakage_audit={"as_of_safe": safe, "decision_time": bundle.decision_time},
                lineage=bundle.lineage + ["Factor: avg_quality * 100"],
            ),
            FactorCandidate(
                factor_id=f"factor-event-pressure-{bundle.bundle_id[-8:]}",
                name="event_pressure",
                family="event_risk",
                description="Positive evidence minus negative controversy pressure.",
                horizon_days=horizon_days,
                universe=list(features),
                exposures={
                    symbol: (values.get("positive_pressure", 0.0) - values.get("negative_pressure", 0.0)) * 100.0
                    for symbol, values in features.items()
                },
                source_item_ids=[event.item_id for event in events],
                leakage_audit={"as_of_safe": safe, "decision_time": bundle.decision_time},
                lineage=bundle.lineage + ["Factor: positive_pressure - negative_pressure"],
            ),
            FactorCandidate(
                factor_id=f"factor-novelty-decay-{bundle.bundle_id[-8:]}",
                name="signal_life",
                family="freshness_decay",
                description="Novelty and freshness adjusted evidence half-life proxy.",
                horizon_days=horizon_days,
                universe=list(features),
                exposures={
                    symbol: (0.65 * values.get("novelty", 0.0) + 0.35 * values.get("avg_confidence", 0.0)) * 100.0
                    for symbol, values in features.items()
                },
                source_item_ids=source_ids,
                leakage_audit={"as_of_safe": safe, "decision_time": bundle.decision_time},
                lineage=bundle.lineage + ["Factor: novelty/confidence blend"],
            ),
        ]
        return candidates

    def _score_factor(
        self,
        candidate: FactorCandidate,
        signal_returns: dict[str, float],
        *,
        dataset_id: str | None = None,
        protection_status: str = "review",
        frequency: str = "daily",
        data_tier: str = "l1",
        blocking_reasons: list[str] | None = None,
    ) -> FactorCard:
        symbols = list(candidate.exposures)
        exposure_values = [float(candidate.exposures.get(symbol, 0.0)) for symbol in symbols]
        returns = [float(signal_returns.get(symbol, 0.0)) for symbol in symbols]
        ic = _corr(exposure_values, returns)
        rank_ic = _corr(_rank(exposure_values), _rank(returns))
        missing = sum(1 for value in exposure_values if value == 0.0) / max(len(exposure_values), 1)
        turnover = _bounded(statistics.pstdev(exposure_values) / 100.0 if len(exposure_values) > 1 else 0.0, 0.0, 2.0)
        sample_ok = len(symbols) >= 3
        leakage_ok = bool(candidate.leakage_audit.get("as_of_safe"))
        cost_ok = turnover <= 0.65
        ic_ok = abs(ic) >= 0.05
        if not leakage_ok:
            status = "rejected"
        elif not sample_ok:
            status = "low_confidence"
        elif ic_ok and cost_ok:
            status = "promoted"
        else:
            status = "research_only"
        gate_blockers = list(blocking_reasons or [])
        if protection_status == "blocked" and status == "promoted":
            status = "research_only"
        failure_modes = []
        if not sample_ok:
            failure_modes.append("small sample; needs Stage 2 independent test split")
        if not ic_ok:
            failure_modes.append("weak IC in current shadow sample")
        if not cost_ok:
            failure_modes.append("high turnover may fail after transaction costs")
        if not leakage_ok:
            failure_modes.append("one or more inputs are not as-of safe")
        if protection_status == "blocked":
            failure_modes.append("research protections blocked promotion; keep factor in research_only mode")
        if gate_blockers:
            failure_modes.extend(gate_blockers)
        registry_gate_status = "pass"
        if protection_status == "blocked" or gate_blockers:
            registry_gate_status = "blocked"
        elif protection_status == "review" or status != "promoted":
            registry_gate_status = "review"
        return FactorCard(
            factor_id=candidate.factor_id,
            name=candidate.name,
            family=candidate.family,
            definition=candidate.description,
            status=status,  # type: ignore[arg-type]
            market="US",
            frequency=frequency if frequency in {"daily", "intraday", "hybrid"} else "daily",  # type: ignore[arg-type]
            data_tier=data_tier if data_tier in {"l1", "l2"} else "l1",  # type: ignore[arg-type]
            dataset_id=dataset_id,
            protection_status=protection_status if protection_status in {"pass", "review", "blocked"} else "review",  # type: ignore[arg-type]
            registry_gate_status=registry_gate_status,  # type: ignore[arg-type]
            blocking_reasons=gate_blockers,
            universe=symbols,
            horizon_days=candidate.horizon_days,
            missing_rate=round(missing, 6),
            ic=round(ic, 6),
            rank_ic=round(rank_ic, 6),
            turnover_estimate=round(turnover, 6),
            transaction_cost_sensitivity="low" if turnover < 0.25 else "medium" if turnover < 0.65 else "high",
            stability_score=round(_bounded(abs(ic) * 0.45 + abs(rank_ic) * 0.35 + (1.0 - missing) * 0.20, 0.0, 1.0), 6),
            sample_count=len(symbols),
            gate_results={
                "sample_ok": sample_ok,
                "leakage_ok": leakage_ok,
                "transaction_cost_ok": cost_ok,
                "ic_ok": ic_ok,
                "promotable": status == "promoted",
            },
            failure_modes=failure_modes,
            lineage=candidate.lineage,
        )

    def _persist_factor_registry(self, cards: list[FactorCard]) -> None:
        for card in cards:
            payload = card.model_dump(mode="json") | {"updated_at": _iso_now()}
            self._persist("quant/factor_registry", card.factor_id, payload)

    def _split_evidence(
        self,
        signal: ResearchSignal,
        items: list[InformationItem],
        events: list[StructuredEvent],
    ) -> tuple[list[InformationItem], list[InformationItem]]:
        event_lookup = {event.item_id: event for event in events}
        main: list[InformationItem] = []
        counter: list[InformationItem] = []
        for item in sorted(items, key=lambda value: value.quality_score, reverse=True):
            event = event_lookup.get(item.item_id)
            if event and event.impact_direction == "negative":
                counter.append(item)
            elif signal.action == "short" and event and event.impact_direction == "positive":
                counter.append(item)
            else:
                main.append(item)
        return main, counter

    def _risk_triggers(self, signal: ResearchSignal, events: list[StructuredEvent]) -> list[str]:
        triggers: list[str] = []
        if float(signal.risk_score or 0.0) >= 62:
            triggers.append(f"Risk score {signal.risk_score:.1f} is above the caution band.")
        if float(signal.confidence or 0.0) < 0.62:
            triggers.append("Model confidence is below the shadow-mode promotion threshold.")
        negative_events = [event for event in events if event.impact_direction == "negative"]
        if negative_events:
            triggers.append(f"{len(negative_events)} negative evidence events require human review before execution.")
        if str(signal.market_data_source or "").lower() == "synthetic":
            triggers.append("Market data source is synthetic/fallback; use as demonstration-grade until refreshed.")
        return triggers or ["No hard risk trigger; still subject to portfolio and execution gates."]

    def _verify_decision(
        self,
        evidence: EvidenceBundle,
        signal: ResearchSignal,
        main: list[InformationItem],
        counter: list[InformationItem],
    ) -> dict[str, Any]:
        safe_ratio = evidence.quality_summary.get("as_of_safe_ratio", 0.0)
        confidence = float(signal.decision_confidence or signal.confidence or 0.0)
        return {
            "sources_present": len(evidence.items) > 0,
            "as_of_safe_ratio": safe_ratio,
            "leakage_pass": safe_ratio >= 0.99,
            "confidence_bounded": 0.0 <= confidence <= 1.0,
            "counter_evidence_present": bool(counter),
            "overconfidence_warning": confidence > 0.88 and bool(counter),
            "execution_guard": "shadow_only_no_order_created",
            "verdict": "review" if safe_ratio < 0.99 or (confidence > 0.88 and counter) else "pass",
            "checks": [
                "source link/provider present",
                "observed_at not after decision_time",
                "main and counter evidence separated",
                "confidence interval attached",
            ],
        }

    def _position_range(self, signal: ResearchSignal) -> dict[str, float]:
        confidence = float(signal.decision_confidence or signal.confidence or 0.0)
        risk = _bounded(float(signal.risk_score or 50.0) / 100.0)
        if signal.action != "long":
            return {"min": 0.0, "max": 0.0}
        center = _bounded(0.02 + confidence * 0.08 - risk * 0.035, 0.0, 0.10)
        return {"min": round(max(0.0, center * 0.55), 4), "max": round(center * 1.25, 4)}

    def _confidence_interval(self, signal: ResearchSignal, simulation: SimulationResult | None) -> dict[str, float]:
        expected = float(signal.expected_return or 0.0)
        if simulation is not None:
            return {
                "lower": simulation.path_summary.get("p05", expected - 0.04),
                "center": simulation.median_return,
                "upper": simulation.path_summary.get("p95", expected + 0.04),
            }
        width = max(float(signal.predicted_volatility_10d or 0.18) * 0.18, 0.02)
        return {"lower": round(expected - width, 6), "center": round(expected, 6), "upper": round(expected + width, 6)}

    def _factor_attribution(self, signal: ResearchSignal, cards: list[FactorCard]) -> dict[str, float]:
        attribution = self._signal_factor_dict(signal)
        for card in cards:
            if card.status == "promoted":
                attribution[f"registry:{card.name}"] = round(card.stability_score, 6)
        return attribution

    def _signal_factor_dict(self, signal: ResearchSignal) -> dict[str, float]:
        total = sum(abs(float(score.contribution or 0.0)) for score in signal.factor_scores) or 1.0
        return {
            score.name: round(float(score.contribution or 0.0) / total, 6)
            for score in signal.factor_scores[:8]
        }

    def _historical_analogs(self, evidence: EvidenceBundle, scenario: SimulationScenario) -> list[dict[str, Any]]:
        analogs: list[dict[str, Any]] = []
        for item in evidence.items[:5]:
            analogs.append(
                {
                    "symbol": item.symbol,
                    "event_type": item.item_type,
                    "title": item.title,
                    "quality_score": item.quality_score,
                    "reason": "Closest available evidence item in current bundle; Stage 2 can replace with true nearest-neighbor event history.",
                }
            )
        if not analogs:
            analogs.append(
                {
                    "symbol": scenario.symbol,
                    "event_type": "synthetic_base_case",
                    "title": scenario.scenario_name,
                    "quality_score": 0.5,
                    "reason": "No evidence bundle was available; deterministic simulator fallback used.",
                }
            )
        return analogs

    def _select_signal(self, signals: list[ResearchSignal], symbol: str) -> ResearchSignal | None:
        symbol_key = symbol.upper().strip()
        for signal in signals:
            if signal.symbol.upper() == symbol_key:
                return signal
        return signals[0] if signals else None

    def _quantile(self, values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        index = _bounded(quantile) * (len(values) - 1)
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return values[int(index)]
        fraction = index - lower
        return values[lower] * (1.0 - fraction) + values[upper] * fraction

    def _dataset_manifest_from_bundle(
        self,
        bundle: EvidenceBundle,
        events: list[StructuredEvent],
        features: dict[str, dict[str, float]],
        *,
        frequency: str = "daily",
        required_data_tier: str = "l1",
        metadata: dict[str, Any] | None = None,
    ) -> DatasetManifest:
        normalized_frequency = frequency if frequency in {"daily", "intraday", "hybrid"} else "daily"
        symbols = sorted(set(bundle.universe) | {item.symbol for item in bundle.items} | set(features))
        providers = list(dict.fromkeys([item.provider for item in bundle.items] + [str(bundle.connector_status.get("mode") or "")]))
        providers = [provider for provider in providers if provider]
        freshness_scores = [float(item.freshness_score or 0.0) for item in bundle.items]
        market_depth_status = self.market_depth_status(
            symbols=symbols[:5],
            require_l2=str(required_data_tier or "l1").lower() == "l2",
        )
        dataset_seed = {
            "decision_time": bundle.decision_time,
            "symbols": symbols,
            "providers": providers,
            "frequency": normalized_frequency,
            "item_count": len(bundle.items),
            "event_count": len(events),
            "market_depth_provider": market_depth_status.get("selected_provider"),
            "required_data_tier": required_data_tier,
        }
        dataset_id = f"dataset-{_stable_hash(dataset_seed)[:12]}"
        return DatasetManifest(
            dataset_id=dataset_id,
            generated_at=_iso_now(),
            market="US",
            frequency=normalized_frequency,  # type: ignore[arg-type]
            data_tier=market_depth_status.get("data_tier", "l1"),  # type: ignore[arg-type]
            as_of_time=bundle.decision_time,
            universe=symbols,
            instruments=[self._instrument_contract(symbol) for symbol in symbols],
            provider_chain=providers,
            freshness={
                "item_count": len(bundle.items),
                "event_count": len(events),
                "avg_freshness_score": round(_mean(freshness_scores), 6),
                "as_of_safe_ratio": bundle.quality_summary.get("as_of_safe_ratio", 0.0),
            },
            market_depth_status=market_depth_status,
            depth_session_ids=[
                str(snapshot.get("snapshot_id") or "")
                for snapshot in market_depth_status.get("latest", [])
                if str(snapshot.get("snapshot_id") or "").strip()
            ],
            provider_capabilities=market_depth_status.get("provider_capabilities", {}),
            lineage=bundle.lineage
            + [
                "L3: US equity instrument contract normalization",
                "L4: dataset manifest with provider chain, freshness, and feature store",
                "L5: shared market-depth contract with explicit data-tier diagnostics",
            ],
            feature_store=features,
            metadata={**(metadata or {}), "required_data_tier": required_data_tier},
        )

    def _protection_report_from_bundle(
        self,
        bundle: EvidenceBundle,
        *,
        dataset_manifest: DatasetManifest,
        formulas: list[str] | None = None,
        labels: list[dict[str, Any]] | None = None,
        timestamps: list[str] | None = None,
        current_constituents_only: bool = False,
        frequency: str = "daily",
        required_data_tier: str = "l1",
    ) -> ResearchProtectionReport:
        formulas = formulas or []
        labels = labels or []
        timestamps = timestamps or []
        decision_dt = _parse_dt(bundle.decision_time) or datetime.now(timezone.utc)
        lookahead_hits = [
            item.item_id
            for item in bundle.items
            if item.leakage_guard != "as_of_safe" or ((_parse_dt(item.observed_at) or decision_dt) > decision_dt)
        ]
        label_hits = [
            label
            for label in labels
            if (_parse_dt(str(label.get("timestamp") or label.get("observed_at") or "")) or decision_dt) > decision_dt
        ]
        timestamp_hits = [value for value in timestamps if (_parse_dt(value) or decision_dt) > decision_dt]
        recursive_flags = [
            formula
            for formula in formulas
            if any(token in str(formula).lower() for token in ("shift(-", "lead(", "future", "t+1", "next_return"))
        ]
        session_misaligned = [
            item.item_id
            for item in bundle.items
            if str(item.metadata.get("timezone") or "America/New_York") not in {"America/New_York", "US/Eastern"}
        ]
        survivorship_warning = bool(current_constituents_only or len(dataset_manifest.universe) <= 3)
        market_depth_status = dict(dataset_manifest.market_depth_status or {})
        latest_depth = list(market_depth_status.get("latest") or [])
        depth_timestamp_violations = [
            str(snapshot.get("snapshot_id") or snapshot.get("timestamp") or "")
            for snapshot in latest_depth
            if (
                _parse_dt(str(snapshot.get("timestamp") or "")) is None
                or (_parse_dt(str(snapshot.get("timestamp") or "")) or decision_dt) > (datetime.now(timezone.utc) + timedelta(minutes=5))
            )
        ]
        allowed_sessions = {"pre", "open", "midday", "close", "post", "regular", "halt", "auction"}
        depth_session_violations = [
            str(snapshot.get("snapshot_id") or snapshot.get("session") or "")
            for snapshot in latest_depth
            if str(snapshot.get("session") or "regular") not in allowed_sessions
        ]
        l2_required = str(required_data_tier or "l1").lower() == "l2"
        l2_available = bool(
            market_depth_status.get("available")
            and market_depth_status.get("is_real_provider")
            and market_depth_status.get("data_tier") == "l2"
        )
        checks = {
            "lookahead": {
                "passed": not lookahead_hits and not label_hits and not timestamp_hits,
                "violations": lookahead_hits + [str(item.get("timestamp") or item.get("observed_at") or "") for item in label_hits] + timestamp_hits,
                "detail": "Evidence and labels must be observed on or before decision_time.",
            },
            "recursive_formula": {
                "passed": not recursive_flags,
                "violations": recursive_flags,
                "detail": "Formula strings may not reference future shifts or lead windows.",
            },
            "as_of_leakage": {
                "passed": bundle.quality_summary.get("as_of_safe_ratio", 0.0) >= 0.99,
                "violations": lookahead_hits,
                "detail": "Evidence bundle must remain as-of safe.",
            },
            "session_alignment": {
                "passed": not session_misaligned,
                "violations": session_misaligned,
                "detail": "US equity research should stay aligned to America/New_York and XNYS sessions.",
            },
            "survivorship_bias": {
                "passed": not survivorship_warning,
                "violations": ["current_constituents_only"] if current_constituents_only else (["small_shadow_universe"] if len(dataset_manifest.universe) <= 3 else []),
                "detail": "Registry promotion should not rely only on current constituents or tiny universes.",
            },
            "l2_availability": {
                "passed": (not l2_required) or l2_available,
                "violations": [] if (not l2_required or l2_available) else ["l2_required_but_unavailable"],
                "detail": "Strategies or research that require L2 must be backed by a real market-depth provider.",
            },
            "depth_timestamp_integrity": {
                "passed": not depth_timestamp_violations,
                "violations": depth_timestamp_violations,
                "detail": "Depth snapshots must carry parseable timestamps and may not drift into the future.",
            },
            "depth_session_alignment": {
                "passed": not depth_session_violations,
                "violations": depth_session_violations,
                "detail": "Depth snapshots must map to supported US equity session labels.",
            },
        }
        blocking_checks = [
            name
            for name, report in checks.items()
            if not bool(report.get("passed")) and name != "survivorship_bias"
        ]
        warnings = []
        if survivorship_warning:
            warnings.append("Universe composition may be survivorship-biased; keep outputs in research_only mode until expanded.")
        if market_depth_status.get("data_tier") != "l2":
            warnings.append("Minute-level or execution-quality diagnostics may be running on explicit L1 proxy mode.")
        blocking_reasons = list(dict.fromkeys(
            [value for name in blocking_checks for value in checks.get(name, {}).get("violations", []) if value]
        ))
        protection_status = "blocked" if blocking_checks else "review" if warnings else "pass"
        return ResearchProtectionReport(
            report_id=f"protection-{dataset_manifest.dataset_id}",
            generated_at=_iso_now(),
            dataset_id=dataset_manifest.dataset_id,
            decision_time=bundle.decision_time,
            market="US",
            frequency=frequency if frequency in {"daily", "intraday", "hybrid"} else "daily",  # type: ignore[arg-type]
            data_tier=dataset_manifest.data_tier,  # type: ignore[arg-type]
            required_data_tier=required_data_tier if required_data_tier in {"l1", "l2"} else "l1",  # type: ignore[arg-type]
            protection_status=protection_status,  # type: ignore[arg-type]
            market_depth_status=market_depth_status,
            checks=checks,
            blocking_checks=blocking_checks,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            lineage=dataset_manifest.lineage
            + [
                "L6: research protections covering lookahead, recursive formulas, as-of leakage, session alignment, survivorship bias, and market depth integrity",
            ],
        )

    def _instrument_contract(self, symbol: str) -> InstrumentContract:
        return InstrumentContract(symbol=str(symbol).upper())

    def _build_intraday_replay(self, signal: ResearchSignal, scenario: SimulationScenario) -> dict[str, Any]:
        base_price = 100.0 + abs(float(signal.expected_return or 0.0)) * 800
        bars: list[dict[str, Any]] = []
        sessions = [
            ("open", "09:30"),
            ("midday", "12:00"),
            ("close", "15:45"),
            ("halt", "13:10"),
            ("high_volatility", "10:05"),
        ]
        for index, (session, clock) in enumerate(sessions):
            spread_bps = float(scenario.slippage_bps or 5.0) + (4.0 if session == "open" else 1.5 if session == "midday" else 3.0)
            impact_bps = float(scenario.transaction_cost_bps or 8.0) * (0.55 if session == "midday" else 0.95)
            fill_probability = _bounded(0.97 - (spread_bps + impact_bps) / 120.0 - (0.25 if session == "halt" else 0.0), 0.2, 0.99)
            bars.append(
                {
                    "timestamp": f"{datetime.now(timezone.utc).date().isoformat()}T{clock}:00-04:00",
                    "session": session,
                    "price": round(base_price * (1 + (index - 2) * 0.0025), 4),
                    "spread_bps": round(spread_bps, 4),
                    "impact_bps": round(impact_bps, 4),
                    "slippage_bps": round(spread_bps * 0.7, 4),
                    "fill_probability": round(fill_probability, 6),
                    "volume": round(90000 * (1.4 if session == "open" else 0.7 if session == "midday" else 1.1), 2),
                }
            )
        return {
            "symbol": signal.symbol,
            "frequencies": ["1m", "5m", "15m"],
            "bars": bars,
            "session_calendar": "XNYS",
            "timezone": "America/New_York",
        }

    def _persist(self, relative_dir: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        target_dir = self.storage_root / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in record_id)
        path = target_dir / f"{safe_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"local_path": str(path), "record_id": safe_id, "record_type": relative_dir}

    def _list_json(self, relative_dir: str, *, limit: int = 20) -> list[dict[str, Any]]:
        target_dir = self.storage_root / relative_dir
        if not target_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(target_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if len(rows) >= max(1, int(limit)):
                break
        return rows

    def _load_decision(self, decision_id: str | None) -> dict[str, Any] | None:
        if not decision_id:
            return None
        safe_id = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in decision_id)
        path = self.storage_root / "quant" / "decision_reports" / f"{safe_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _load_evidence(self, evidence_run_id: str | None) -> dict[str, Any] | None:
        if not evidence_run_id:
            return None
        safe_id = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in evidence_run_id)
        candidates = [
            self.storage_root / "intelligence" / "evidence_lake" / f"{safe_id}.json",
            self.storage_root / "intelligence" / "connector_runs" / f"{safe_id}.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if "bundle_id" in payload and "items" in payload:
                return payload
            if "items" in payload:
                items = [
                    self._make_item(
                        item_type=str(item.get("item_type") or "news"),
                        provider=str(item.get("provider") or "connector_run"),
                        source=str(item.get("source") or item.get("provider") or "connector_run"),
                        url=item.get("url"),
                        symbol=str(item.get("symbol") or "AAPL"),
                        company_name=str(item.get("company_name") or item.get("symbol") or "Unknown"),
                        title=str(item.get("title") or "Connector evidence"),
                        summary=str(item.get("summary") or item.get("title") or ""),
                        published_at=item.get("published_at"),
                        observed_at=str(item.get("observed_at") or payload.get("decision_time") or payload.get("generated_at") or _iso_now()),
                        confidence=float(item.get("confidence") or 0.66),
                        checksum=item.get("checksum"),
                        metadata=item.get("metadata") or {},
                    ).model_dump(mode="json")
                    for item in payload.get("items", [])
                ]
                return {
                    "bundle_id": safe_id,
                    "generated_at": payload.get("generated_at") or _iso_now(),
                    "decision_time": payload.get("decision_time") or payload.get("generated_at") or _iso_now(),
                    "universe": payload.get("universe") or sorted({item.get("symbol") for item in payload.get("items", []) if item.get("symbol")}),
                    "query": "connector run evidence",
                    "items": items,
                    "connector_status": payload.get("summary") or {},
                    "quality_summary": self._quality_summary([InformationItem.model_validate(item) for item in items]),
                    "lineage": payload.get("lineage") or ["connector run loaded as evidence bundle"],
                }
        return None

    def _live_data_age(self, items: list[InformationItem], decision_time: str) -> dict[str, Any]:
        cutoff = _parse_dt(decision_time) or datetime.now(timezone.utc)
        ages: list[float] = []
        for item in items:
            observed = _parse_dt(item.observed_at)
            if observed is not None:
                ages.append(max((cutoff - observed).total_seconds() / 3600.0, 0.0))
        return {
            "max_age_hours": round(max(ages), 4) if ages else None,
            "avg_age_hours": round(_mean(ages), 4) if ages else None,
            "item_count": len(items),
        }

    def _event_adjustment(self, evidence: EvidenceBundle, event_id: str | None) -> float:
        if not event_id:
            return 0.0
        events = self.extract_events(evidence)
        for event in events:
            if event.event_id == event_id or event.item_id == event_id:
                sign = -1.0 if event.impact_direction == "negative" else 1.0 if event.impact_direction == "positive" else 0.0
                return sign * float(event.impact_strength) * 0.015
        return 0.0

    def _outcome_summary(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        hits = [record.get("direction_hit") for record in records if record.get("direction_hit") is not None]
        briers = [float(record.get("brier_component")) for record in records if record.get("brier_component") is not None]
        excess = [float(record.get("excess_return") or 0.0) for record in records]
        return {
            "generated_at": _iso_now(),
            "record_count": len(records),
            "hit_rate": round(sum(1 for hit in hits if hit) / max(len(hits), 1), 6) if hits else None,
            "mean_brier": round(_mean(briers), 6) if briers else None,
            "mean_excess_return": round(_mean(excess), 6) if excess else None,
            "drawdown_breaches": sum(1 for record in records if record.get("drawdown_breach")),
            "shadow_mode": True,
            "policy": "Use calibration data to create Stage 2/3 retraining queues; do not execute trades from outcomes.",
        }
