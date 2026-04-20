from fastapi.testclient import TestClient

import gateway.api.routers.trading as trading_router
import gateway.main as main_module


class _TradingStub:
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
        return {"review": {"review_id": "review-1", "report_text": "paper-only", "pnl": 12.5}}

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
        return {
            "bundle_id": "bundle-1",
            "symbol": kwargs["symbol"],
            "debate": self.run_debate(symbol=kwargs["symbol"]),
            "risk": self.evaluate_risk(symbol=kwargs["symbol"]),
            "execution": {"execution_id": "trade-1", "submitted": True, "status": "submitted"},
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
            "notifier": {"telegram_configured": False, "mode": "paper_shadow_notify"},
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

    job = client.post("/api/v1/trading/jobs/run/premarket_agent", json={})
    assert job.status_code == 200
    assert job.json()["job_name"] == "premarket_agent"
