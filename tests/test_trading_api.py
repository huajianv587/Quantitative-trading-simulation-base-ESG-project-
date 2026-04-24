from fastapi.testclient import TestClient

import gateway.api.routers.trading as trading_router
import gateway.main as main_module


class _TradingStub:
    def __init__(self):
        self._policy = {
            "policy_id": "autopilot-default",
            "generated_at": "2026-04-20T12:00:00Z",
            "execution_mode": "paper",
            "execution_permission": "auto_submit",
            "auto_submit_enabled": False,
            "paper_auto_submit_enabled": False,
            "armed": False,
            "daily_budget_cap": 10000.0,
            "per_trade_cap": 2500.0,
            "max_open_positions": 5,
            "max_symbol_weight": 0.2,
            "allowed_universe": ["AAPL", "NVDA", "TSLA", "SPY"],
            "allowed_strategies": ["esg_multifactor_long_only", "regime_rotation"],
            "require_human_review_above": 7500.0,
            "drawdown_limit": 0.06,
            "daily_loss_limit": 1500.0,
            "signal_ttl": 180,
            "kill_switch": False,
            "protections": ["judge_gate", "risk_gate"],
            "warnings": [],
        }
        self._strategies = [
            {
                "strategy_id": "esg_multifactor_long_only",
                "display_name": "ESG Multi-Factor Long Only",
                "status": "active",
                "factor_dependencies": ["quality", "value", "momentum", "esg_delta"],
                "required_frequency": "daily",
                "required_data_tier": "l1",
                "registry_gate_status": "pass",
                "eligible_for_execution": True,
                "blocking_reasons": [],
                "latest_dataset_id": "dataset-aapl",
                "latest_protection_status": "pass",
                "latest_l2_status": "pass",
                "bound_rl_run_id": None,
                "risk_profile": "balanced",
                "capital_allocation": 0.34,
                "allowed_symbols": ["AAPL", "MSFT", "NVDA"],
                "paper_ready": True,
                "requires_debate": True,
                "requires_risk_approval": True,
            }
        ]
        self._sync_policy_runtime()

    def _sync_policy_runtime(self):
        requested_mode = str(self._policy.get("execution_mode") or "paper").lower()
        paper_ready = True
        live_available = False
        live_ready = False
        block_reason = None
        next_actions = []
        if requested_mode == "live" and not live_available:
            block_reason = "live_credentials_missing"
            next_actions = ["add_live_alpaca_keys", "switch_to_paper_mode"]
        effective_mode = "live" if requested_mode == "live" and live_ready else "paper"
        warnings = []
        if block_reason:
            warnings.append("live_mode_selected")
            warnings.append(block_reason)
        self._policy.update(
            {
                "requested_mode": requested_mode,
                "effective_mode": effective_mode,
                "paper_ready": paper_ready,
                "live_ready": live_ready,
                "live_available": live_available,
                "block_reason": block_reason,
                "next_actions": next_actions,
                "warnings": warnings,
            }
        )

    def execution_intent_contract(self):
        return {
            "intent_id": "intent-execution-sample",
            "created_at": "2026-04-20T12:00:00Z",
            "symbol": "AAPL",
            "requested_action": "long",
            "approved_action": "long",
            "execution_mode": "paper",
            "strategy_slots": ["esg_multifactor_long_only"],
            "factor_dependencies": ["quality", "value", "momentum", "esg_delta"],
            "recommended_weight": 0.05,
            "recommended_notional": 5000.0,
            "signal_ttl_minutes": 180,
            "guards": ["judge_gate", "risk_gate", "auto_submit"],
            "dataset_id": "dataset-aapl",
            "protection_status": "pass",
            "frequency": "daily",
            "data_tier": "l1",
            "registry_gate_status": "pass",
            "blocking_reasons": [],
            "metadata": {"sample": True},
        }

    def execution_result_contract(self):
        return {
            "execution_id": "trade-1",
            "generated_at": "2026-04-20T12:00:00Z",
            "symbol": "AAPL",
            "status": "submitted",
            "venue": "alpaca",
            "execution_mode": "paper",
            "submitted": True,
            "auto_submit": True,
            "requested_action": "long",
            "approved_action": "long",
            "verdict": "approve",
            "dataset_id": "dataset-aapl",
            "protection_status": "pass",
            "frequency": "daily",
            "data_tier": "l1",
            "registry_gate_status": "pass",
            "blocking_reasons": [],
            "order_payload": {"symbol": "AAPL", "side": "buy", "notional": 5000},
            "receipt": {"id": "paper-aapl-1"},
            "warnings": [],
            "policy_gate_warnings": [],
            "next_action": "monitor_fill_and_review_outcome",
            "trigger_event": {},
            "metadata": {"sample": True},
        }

    def factor_pipeline_manifest(self):
        return {
            "manifest_id": "factor-pipeline-current",
            "generated_at": "2026-04-20T12:00:00Z",
            "symbol": "AAPL",
            "strategy_slots": ["esg_multifactor_long_only"],
            "factor_dependencies": ["quality", "value", "momentum", "esg_delta"],
            "stages": [
                {"stage": "feature_build", "status": "ready"},
                {"stage": "factor_gate", "status": "ready"},
                {"stage": "strategy_slot", "status": "ready"},
                {"stage": "registry_gate", "status": "ready"},
            ],
            "warnings": [],
            "next_action": "Compare factor gate output with strategy allocation before promotion.",
            "market_depth_status": self.market_depth_status(),
        }

    def market_depth_status(self):
        return {
            "generated_at": "2026-04-20T12:00:00Z",
            "selected_provider": "fake_l2",
            "configured_providers": ["fake_l2"],
            "provider_capabilities": {"fake_l2": {"available": True, "history_ready": True, "realtime_ready": True}},
            "available": True,
            "history_ready": True,
            "realtime_ready": True,
            "data_tier": "l1",
            "eligibility_status": "review",
            "blocking_reasons": [],
            "latest": [{"symbol": "AAPL", "spread_bps": 4.8, "session": "midday"}],
        }

    def list_strategy_eligibility(self, **kwargs):
        return {
            "generated_at": "2026-04-20T12:00:00Z",
            "symbol": kwargs.get("symbol"),
            "eligible_count": 1,
            "blocked_count": 0,
            "review_count": 0,
            "market_depth_status": self.market_depth_status(),
            "strategies": self._strategies,
        }

    def schedule_status(self):
        return {
            "jobs": [
                {"job_name": "premarket_agent", "next_run": "2026-04-20T08:30:00-04:00"},
                {"job_name": "review_agent", "next_run": "2026-04-20T21:30:00-04:00"},
            ],
            "recent_runs": [],
        }

    def list_watchlist(self):
        return {"watchlist": [{"symbol": "AAPL", "enabled": True}], "count": 1}

    def add_watchlist_symbol(self, **kwargs):
        return {"watchlist_item": {"symbol": kwargs["symbol"], "enabled": kwargs.get("enabled", True)}, "watchlist": [{"symbol": kwargs["symbol"]}]}

    def latest_review(self):
        return {"review": {"review_id": "review-1", "report_text": "guardrailed execution review", "pnl": 12.5}}

    def alerts_today(self):
        return {"alerts": [{"alert_id": "alert-1", "symbol": "AAPL", "trigger_type": "price_move"}], "alert_count": 1}

    def run_sentiment(self, **kwargs):
        return {"snapshot_id": "sent-1", "universe": kwargs.get("universe") or ["AAPL"], "headline_count": 3}

    def run_debate(self, **kwargs):
        return {
            "debate_id": "debate-1",
            "symbol": kwargs["symbol"],
            "bull_thesis": "bull",
            "bear_thesis": "bear",
            "turns": [{"round_number": 1, "bull_point": "a", "bear_point": "b", "evidence_focus": [], "confidence_shift": 0.1}],
            "conflict_points": ["conflict"],
            "consensus_points": ["consensus"],
            "judge_verdict": "long",
            "judge_confidence": 0.72,
            "dispute_score": 0.18,
            "recommended_action": "long",
            "confidence_shift": 0.21,
            "requires_human_review": False,
            "factor_count": 4,
            "expected_edge": 0.03,
        }

    def debate_runs(self, **kwargs):
        return {"count": 1, "debates": [self.run_debate(symbol=kwargs.get("symbol") or "AAPL")]}

    def evaluate_risk(self, **kwargs):
        return {
            "approval_id": "risk-1",
            "symbol": kwargs["symbol"],
            "verdict": "approve",
            "approved_action": "long",
            "requested_action": "long",
            "kelly_fraction": 0.08,
            "recommended_weight": 0.05,
            "recommended_notional": 5000,
            "drawdown_estimate": 0.01,
            "signal_ttl_minutes": kwargs.get("signal_ttl_minutes", 180),
            "risk_flags": [],
            "hard_blocks": [],
            "rationale": ["clean"],
        }

    def risk_board(self, **kwargs):
        return {
            "controls": {"kill_switch_enabled": False, "single_name_weight_cap": 0.26, "default_broker": "alpaca", "default_mode": "paper"},
            "approvals": [self.evaluate_risk(symbol=kwargs.get("symbol") or "AAPL")],
            "latest_approval": self.evaluate_risk(symbol=kwargs.get("symbol") or "AAPL"),
            "alerts": [{"symbol": "AAPL", "trigger_type": "price_move", "agent_analysis": "watch"}],
        }

    def run_trading_cycle(self, **kwargs):
        if self._policy["requested_mode"] == "live" and self._policy["block_reason"]:
            return {
                "bundle_id": "bundle-live-blocked",
                "symbol": kwargs["symbol"],
                "execution": {
                    **self.execution_result_contract(),
                    "status": "blocked",
                    "submitted": False,
                    "execution_mode": self._policy["effective_mode"],
                    "warnings": [self._policy["block_reason"]],
                    "policy_gate_warnings": [self._policy["block_reason"]],
                    "next_action": self._policy["next_actions"][0],
                },
                "execution_intent": self.execution_intent_contract(),
                "execution_result": {
                    **self.execution_result_contract(),
                    "status": "blocked",
                    "submitted": False,
                    "execution_mode": self._policy["effective_mode"],
                    "warnings": [self._policy["block_reason"]],
                    "policy_gate_warnings": [self._policy["block_reason"]],
                    "next_action": self._policy["next_actions"][0],
                },
                "execution_path": self.execution_path_status(),
                "autopilot_policy": self._policy,
                "policy_gate_warnings": [self._policy["block_reason"]],
                "next_actions": self._policy["next_actions"],
            }
        execution_result = self.execution_result_contract()
        return {
            "bundle_id": "bundle-1",
            "symbol": kwargs["symbol"],
            "debate": self.run_debate(symbol=kwargs["symbol"]),
            "risk": self.evaluate_risk(symbol=kwargs["symbol"]),
            "execution": execution_result,
            "execution_intent": self.execution_intent_contract(),
            "execution_result": execution_result,
            "factor_pipeline_manifest": self.factor_pipeline_manifest(),
        }

    def monitor_status(self):
        return {"running": False, "stream_mode": "idle", "trigger_count": 0}

    async def start_intraday_monitor(self):
        return {"running": True, "stream_mode": "websocket", "trigger_count": 0}

    async def stop_intraday_monitor(self):
        return {"running": False, "stream_mode": "idle", "trigger_count": 0}

    async def run_scheduled_job(self, job_name, scheduled_for):
        return {"run_id": f"job-{job_name}", "job_name": job_name, "scheduled_for": scheduled_for, "status": "completed"}

    def trading_ops_snapshot(self):
        return {
            "schedule": self.schedule_status(),
            "monitor": self.monitor_status(),
            "watchlist": self.list_watchlist(),
            "today_alerts": self.alerts_today(),
            "latest_review": self.latest_review(),
            "debates": self.debate_runs(symbol="AAPL"),
            "risk": self.risk_board(symbol="AAPL"),
            "autopilot_policy": self._policy,
            "strategies": {"count": len(self._strategies), "strategies": self._strategies, "eligibility": self.list_strategy_eligibility()},
            "strategy_eligibility": self.list_strategy_eligibility(),
            "market_depth": self.market_depth_status(),
            "execution_path": self.execution_path_status(),
            "factor_pipeline": self.factor_pipeline_manifest(),
            "fusion_manifest": self.fusion_reference_manifest(),
            "notifier": {"telegram_configured": False, "mode": "shadow_notify"},
        }

    def get_autopilot_policy(self):
        return self._policy

    def save_autopilot_policy(self, payload):
        self._policy.update(payload)
        self._sync_policy_runtime()
        return self._policy

    def arm_autopilot(self, *, armed):
        if armed and self._policy["requested_mode"] == "live" and self._policy["block_reason"]:
            self._policy["armed"] = False
        else:
            self._policy["armed"] = armed
        self._sync_policy_runtime()
        return self._policy

    def list_strategies(self):
        return {"count": len(self._strategies), "strategies": self._strategies, "eligibility": self.list_strategy_eligibility()}

    def toggle_strategy(self, *, strategy_id, status):
        self._strategies[0]["status"] = status
        return {"strategy": self._strategies[0]}

    def allocate_strategy(self, *, strategy_id, capital_allocation, max_symbols, status):
        self._strategies[0]["capital_allocation"] = capital_allocation
        return {"allocation": {"strategy_id": strategy_id, "capital_allocation": capital_allocation, "max_symbols": max_symbols, "status": status}}

    def execution_path_status(self):
        return {
            "generated_at": "2026-04-20T12:00:00Z",
            "mode": self._policy["effective_mode"],
            "requested_mode": self._policy["requested_mode"],
            "effective_mode": self._policy["effective_mode"],
            "paper_ready": self._policy["paper_ready"],
            "live_ready": self._policy["live_ready"],
            "live_available": self._policy["live_available"],
            "block_reason": self._policy["block_reason"],
            "next_actions": self._policy["next_actions"],
            "armed": self._policy["armed"],
            "daily_budget_cap": self._policy["daily_budget_cap"],
            "budget_remaining": self._policy["daily_budget_cap"],
            "judge_passed": True,
            "risk_passed": True,
            "kill_switch": False,
            "current_stage": "blocked" if self._policy["block_reason"] else "idle",
            "stages": [{"stage": "scan", "status": "ready"}, {"stage": "factors", "status": "ready"}, {"stage": "l2_ready", "status": "guarded"}, {"stage": "judge", "status": "passed"}, {"stage": "risk", "status": "passed"}, {"stage": "submit", "status": "ready"}],
            "lineage": ["scan", "factors", "l2_ready", "debate", "judge", "risk", "submit", "monitor", "review"],
            "warnings": [self._policy["block_reason"]] if self._policy["block_reason"] else [],
        }

    def dashboard_state(self, provider="auto"):
        return {
            "generated_at": "2026-04-20T12:00:00Z",
            "phase": "degraded",
            "ready": False,
            "symbol": "AAPL",
            "source": "unknown",
            "selected_provider": provider,
            "source_chain": ["alpaca", "twelvedata", "yfinance", "cache", "synthetic"],
            "provider_status": {"available": True, "provider": "alpaca", "selected_provider": provider},
            "degraded_from": "alpaca",
            "fallback_preview": {
                "symbol": "AAPL",
                "source": "unknown",
                "source_chain": ["alpaca", "twelvedata", "yfinance", "cache", "synthetic"],
                "reason": ["provider_connected_but_no_payload", "provider_degraded_from_alpaca"],
                "next_actions": ["refresh_dashboard", "open_market_radar"],
            },
        }

    def fusion_reference_manifest(self):
        return {
            "manifest_id": "fusion-reference-default",
            "generated_at": "2026-04-20T12:00:00Z",
            "items": [{"source_project": "Lean", "capability": "order lifecycle", "target_surface": "Trading Ops", "status": "implemented"}],
            "execution_intent_contract": self.execution_intent_contract(),
            "execution_result_contract": self.execution_result_contract(),
            "factor_pipeline_manifest": self.factor_pipeline_manifest(),
        }


def test_trading_endpoints_and_aliases(monkeypatch):
    monkeypatch.setattr(trading_router, "_trading_service", lambda: _TradingStub())
    client = TestClient(main_module.app)

    schedule = client.get("/api/v1/trading/schedule/status")
    assert schedule.status_code == 200
    assert schedule.json()["jobs"][0]["job_name"] == "premarket_agent"

    schedule_alias = client.get("/schedule/status")
    assert schedule_alias.status_code == 200

    watchlist = client.post("/api/v1/trading/watchlist/add", json={"symbol": "NVDA"})
    assert watchlist.status_code == 200
    assert watchlist.json()["watchlist_item"]["symbol"] == "NVDA"

    watchlist_alias = client.post("/watchlist/add", json={"symbol": "TSLA"})
    assert watchlist_alias.status_code == 200

    latest_review = client.get("/review/latest")
    assert latest_review.status_code == 200
    assert latest_review.json()["review"]["review_id"] == "review-1"

    alerts = client.get("/alerts/today")
    assert alerts.status_code == 200
    assert alerts.json()["alert_count"] == 1

    sentiment = client.post("/api/v1/trading/sentiment/run", json={"universe": ["AAPL", "NVDA"]})
    assert sentiment.status_code == 200
    assert sentiment.json()["snapshot_id"] == "sent-1"

    debate = client.post("/api/v1/trading/debate/run", json={"symbol": "AAPL"})
    assert debate.status_code == 200
    assert debate.json()["judge_verdict"] == "long"

    risk = client.post("/api/v1/trading/risk/evaluate", json={"symbol": "AAPL"})
    assert risk.status_code == 200
    assert risk.json()["verdict"] == "approve"

    cycle = client.post("/api/v1/trading/cycle/run", json={"symbol": "AAPL"})
    assert cycle.status_code == 200
    assert cycle.json()["execution"]["submitted"] is True
    assert cycle.json()["execution_intent"]["intent_id"] == "intent-execution-sample"
    assert cycle.json()["execution_result"]["status"] == "submitted"
    assert cycle.json()["factor_pipeline_manifest"]["manifest_id"] == "factor-pipeline-current"


def test_trading_monitor_and_ops_snapshot(monkeypatch):
    monkeypatch.setattr(trading_router, "_trading_service", lambda: _TradingStub())
    client = TestClient(main_module.app)

    status = client.get("/api/v1/trading/monitor/status")
    assert status.status_code == 200
    assert status.json()["stream_mode"] == "idle"

    start = client.post("/api/v1/trading/monitor/start")
    assert start.status_code == 200
    assert start.json()["running"] is True

    stop = client.post("/api/v1/trading/monitor/stop")
    assert stop.status_code == 200
    assert stop.json()["running"] is False

    ops = client.get("/api/v1/trading/ops/snapshot")
    assert ops.status_code == 200
    payload = ops.json()
    assert "schedule" in payload
    assert "watchlist" in payload
    assert "latest_review" in payload
    assert "market_depth" in payload
    assert "strategy_eligibility" in payload
    assert payload["factor_pipeline"]["manifest_id"] == "factor-pipeline-current"

    job = client.post("/api/v1/trading/jobs/run/premarket_agent", json={})
    assert job.status_code == 200
    assert job.json()["job_name"] == "premarket_agent"


def test_autopilot_strategy_and_dashboard_routes(monkeypatch):
    stub = _TradingStub()
    monkeypatch.setattr(trading_router, "_trading_service", lambda: stub)
    client = TestClient(main_module.app)

    policy = client.get("/api/v1/trading/autopilot/policy")
    assert policy.status_code == 200
    assert policy.json()["policy_id"] == "autopilot-default"
    assert policy.json()["requested_mode"] == "paper"
    assert policy.json()["effective_mode"] == "paper"
    assert policy.json()["paper_ready"] is True
    assert policy.json()["live_available"] is False

    saved = client.post("/api/v1/trading/autopilot/policy", json={"daily_budget_cap": 12000, "auto_submit_enabled": True})
    assert saved.status_code == 200
    assert saved.json()["daily_budget_cap"] == 12000
    assert saved.json()["auto_submit_enabled"] is True

    arm = client.post("/api/v1/trading/autopilot/arm", json={"armed": True})
    assert arm.status_code == 200
    assert arm.json()["armed"] is True
    assert arm.json()["auto_submit_enabled"] is True

    disarm = client.post("/api/v1/trading/autopilot/disarm", json={"armed": False})
    assert disarm.status_code == 200
    assert disarm.json()["armed"] is False
    assert disarm.json()["auto_submit_enabled"] is True

    strategies = client.get("/api/v1/trading/strategies")
    assert strategies.status_code == 200
    assert strategies.json()["count"] == 1
    assert strategies.json()["eligibility"]["eligible_count"] == 1

    eligibility = client.get("/api/v1/trading/strategies/eligibility?symbol=AAPL")
    assert eligibility.status_code == 200
    assert eligibility.json()["market_depth_status"]["selected_provider"] == "fake_l2"

    toggle = client.post("/api/v1/trading/strategies/esg_multifactor_long_only/toggle", json={"status": "paused"})
    assert toggle.status_code == 200
    assert toggle.json()["strategy"]["status"] == "paused"

    allocation = client.post("/api/v1/trading/strategies/esg_multifactor_long_only/allocation", json={"capital_allocation": 0.42, "max_symbols": 8, "status": "active"})
    assert allocation.status_code == 200
    assert allocation.json()["allocation"]["capital_allocation"] == 0.42

    execution_path = client.get("/api/v1/trading/execution-path/status")
    assert execution_path.status_code == 200
    assert execution_path.json()["mode"] == "paper"
    assert execution_path.json()["requested_mode"] == "paper"
    assert execution_path.json()["effective_mode"] == "paper"
    assert any(stage["stage"] == "l2_ready" for stage in execution_path.json()["stages"])

    dashboard_state = client.get("/api/v1/trading/dashboard/state?provider=alpaca")
    assert dashboard_state.status_code == 200
    assert dashboard_state.json()["phase"] == "degraded"
    assert dashboard_state.json()["selected_provider"] == "alpaca"
    assert dashboard_state.json()["source_chain"][0] == "alpaca"

    fusion = client.get("/api/v1/trading/fusion/status")
    assert fusion.status_code == 200
    assert fusion.json()["manifest_id"] == "fusion-reference-default"
    assert fusion.json()["execution_intent_contract"]["intent_id"] == "intent-execution-sample"
    assert fusion.json()["execution_result_contract"]["status"] == "submitted"
    assert fusion.json()["factor_pipeline_manifest"]["manifest_id"] == "factor-pipeline-current"


def test_live_mode_is_saved_but_execution_stays_blocked_until_ready(monkeypatch):
    stub = _TradingStub()
    monkeypatch.setattr(trading_router, "_trading_service", lambda: stub)
    client = TestClient(main_module.app)

    saved = client.post("/api/v1/trading/autopilot/policy", json={"execution_mode": "live"})
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["execution_mode"] == "live"
    assert payload["requested_mode"] == "live"
    assert payload["effective_mode"] == "paper"
    assert payload["live_ready"] is False
    assert payload["live_available"] is False
    assert payload["block_reason"] == "live_credentials_missing"

    arm = client.post("/api/v1/trading/autopilot/arm", json={"armed": True})
    assert arm.status_code == 200
    assert arm.json()["armed"] is False
    assert arm.json()["block_reason"] == "live_credentials_missing"

    cycle = client.post("/api/v1/trading/cycle/run", json={"symbol": "AAPL"})
    assert cycle.status_code == 200
    assert cycle.json()["execution"]["submitted"] is False
    assert cycle.json()["execution"]["status"] == "blocked"
    assert cycle.json()["execution"]["policy_gate_warnings"] == ["live_credentials_missing"]
