import asyncio

from gateway.trading.reward_bandit import (
    build_horizon_states,
    compute_reward_score,
    default_bandit_state,
    settle_candidate_with_bars,
    update_bandit_state,
)
from gateway.trading.scheduler import TradingScheduler
from gateway.trading.service import TradingAgentService


class _FakePaperRewardStore:
    def __init__(self):
        self.candidates = {}
        self.bandit_state = None
        self.job_runs = []

    def list_watchlist(self, enabled_only=True):
        return [{"symbol": "AAPL"}, {"symbol": "NVDA"}]

    def get_paper_reward_bandit_state(self):
        return self.bandit_state

    def save_paper_reward_bandit_state(self, payload):
        self.bandit_state = dict(payload)
        return self.bandit_state

    def save_paper_reward_candidate(self, candidate):
        payload = candidate.model_dump(mode="json")
        self.candidates[payload["candidate_id"]] = payload
        return payload

    def get_paper_reward_candidate(self, candidate_id):
        return self.candidates.get(candidate_id)

    def list_paper_reward_candidates(self, *, limit=200, status=None):
        rows = list(self.candidates.values())
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows[:limit]

    def save_job_run(self, run):
        payload = run.model_dump()
        self.job_runs.append(payload)
        return payload


class _FakeMarketData:
    def get_daily_bars(self, symbol, **kwargs):
        return [
            {"timestamp": "2026-01-05T21:00:00+00:00", "close": 101.0},
            {"timestamp": "2026-01-06T21:00:00+00:00", "close": 102.0},
            {"timestamp": "2026-01-07T21:00:00+00:00", "close": 103.0},
            {"timestamp": "2026-01-08T21:00:00+00:00", "close": 104.0},
            {"timestamp": "2026-01-09T21:00:00+00:00", "close": 105.0},
        ]


class _FakeQuantSystem:
    default_benchmark = "SPY"
    default_broker = "alpaca"

    def __init__(self):
        self.market_data = _FakeMarketData()
        self.persisted = []

    def create_execution_plan(self, **kwargs):
        assert kwargs["reward_candidate_mode"] is True
        symbols = ["AAPL", "NVDA", "MSFT", "TSLA", "SPY"]
        orders = [
            {
                "symbol": symbol,
                "side": "buy",
                "quantity": 1,
                "target_weight": 0.1,
                "limit_price": 100.0,
                "notional": 1.0,
                "client_order_id": f"client-{symbol.lower()}",
                "status": "validated",
                "estimated_slippage_bps": 4,
                "estimated_impact_bps": 3,
                "expected_fill_probability": 0.9,
                "canary_bucket": "full_release",
            }
            for symbol in symbols
        ]
        positions = [
            {
                "symbol": symbol,
                "weight": 0.1,
                "expected_return": 0.02 + index * 0.001,
                "risk_budget": 0.75,
                "score": 70 + index,
                "side": "long",
                "strategy_bucket": "paper_reward_test",
            }
            for index, symbol in enumerate(symbols)
        ]
        return {
            "execution_id": "execution-reward-test",
            "broker_id": "alpaca",
            "broker_status": "planned",
            "mode": "paper",
            "ready": True,
            "orders": orders,
            "portfolio": {"positions": positions},
            "per_order_notional": 1.0,
            "order_type": "market",
            "time_in_force": "day",
            "extended_hours": False,
            "submitted_orders": [],
            "warnings": [],
            "journal": {"current_state": "validated", "records": []},
        }

    def _prepare_broker_adapter(self, broker, mode):
        return object(), "paper"

    def _build_execution_journal(self, **kwargs):
        return {"current_state": "validated", "records": []}

    def _submit_broker_orders(self, **kwargs):
        payload = kwargs["payload"]
        receipts = []
        for order in payload["orders"]:
            order["status"] = "accepted"
            order["broker_order_id"] = f"broker-{order['symbol'].lower()}"
            order["submitted_at"] = "2026-01-02T14:30:00+00:00"
            receipt = {
                "id": order["broker_order_id"],
                "client_order_id": order["client_order_id"],
                "symbol": order["symbol"],
                "status": "accepted",
                "submitted_at": order["submitted_at"],
                "filled_avg_price": "100.0",
            }
            receipts.append(receipt)
        payload["submitted"] = True
        payload["broker_status"] = "submitted"
        payload["submitted_orders"] = receipts

    def _persist_execution_payload(self, payload, journal):
        self.persisted.append({"payload": payload, "journal": journal})


def test_reward_score_penalizes_bad_outcomes_and_costs():
    positive = compute_reward_score(
        directional_return=0.025,
        transaction_cost=0.001,
        volatility=0.12,
        esg_score=75,
    )
    negative = compute_reward_score(
        directional_return=-0.025,
        transaction_cost=0.001,
        volatility=0.12,
        esg_score=75,
    )

    assert positive["score"] > 0
    assert negative["score"] < 0
    assert positive["score"] > negative["score"]


def test_settlement_waits_for_missing_n3_and_n5_closes():
    candidate = {
        "candidate_id": "reward-aapl-1",
        "batch_id": "batch-1",
        "created_at": "2026-01-02T14:30:00+00:00",
        "symbol": "AAPL",
        "action": "long",
        "entry_price": 100.0,
        "entry_at": "2026-01-02T14:30:00+00:00",
        "features": {
            "estimated_slippage_bps": 5,
            "estimated_impact_bps": 2,
            "predicted_volatility_10d": 0.15,
            "overall_score": 72,
        },
        "settlements": build_horizon_states("2026-01-02T14:30:00+00:00"),
        "status": "pending",
    }

    settled, changed = settle_candidate_with_bars(
        candidate,
        [{"timestamp": "2026-01-05T21:00:00+00:00", "close": 103.0}],
    )

    assert changed is True
    assert settled["settlements"]["n1"]["status"] == "settled"
    assert settled["settlements"]["n3"]["status"] == "pending"
    assert settled["settlements"]["n5"]["status"] == "pending"
    assert settled["status"] == "partially_settled"
    assert settled["partial_score"] is not None
    assert settled.get("score") is None


def test_bandit_update_records_arm_pull_and_reward():
    state = default_bandit_state()
    updated = update_bandit_state(
        state,
        {
            "symbol": "AAPL",
            "action": "long",
            "score": 0.018,
            "features": {
                "expected_return": 0.02,
                "confidence": 0.7,
                "overall_score": 75,
                "risk_score": 32,
                "target_weight": 0.1,
            },
        },
    )

    assert updated["arms"]["AAPL:long"]["pulls"] == 1
    assert updated["arms"]["AAPL:long"]["last_score"] == 0.018
    assert updated["arms"]["AAPL:long"]["avg_reward"] == 0.018


def test_scheduler_contains_paper_reward_candidate_and_settlement_jobs():
    candidate_spec = TradingScheduler.JOB_SPECS["paper_reward_candidates_run"]
    assert candidate_spec["hour"] == 10
    assert candidate_spec["minute"] == 0

    spec = TradingScheduler.JOB_SPECS["paper_reward_settlement"]
    assert spec["hour"] == 21
    assert spec["minute"] == 45


def test_scheduled_paper_reward_candidates_job_uses_default_run_params():
    service = object.__new__(TradingAgentService)
    service.store = _FakePaperRewardStore()
    service._is_market_day = lambda: True
    calls = []

    def _run_candidates(**kwargs):
        calls.append(kwargs)
        return {
            "batch_id": "reward-batch-auto",
            "execution_id": "execution-auto",
            "submitted_count": 5,
        }

    service.run_paper_reward_candidates = _run_candidates
    result = asyncio.run(
        service.run_scheduled_job(
            "paper_reward_candidates_run",
            "2026-01-05T15:00:00+00:00",
        )
    )

    assert calls == [
        {
            "universe": None,
            "max_candidates": 5,
            "per_order_notional": None,
            "benchmark": "SPY",
            "allow_duplicates": False,
        }
    ]
    assert result["status"] == "completed"
    assert result["auto_submit_triggered"] is True
    assert result["result_ref"]["record_id"] == "reward-batch-auto"
    assert result["result_ref"]["execution_id"] == "execution-auto"


def test_paper_reward_service_full_feedback_loop_with_mocks():
    service = object.__new__(TradingAgentService)
    service.quant_system = _FakeQuantSystem()
    service.store = _FakePaperRewardStore()

    run = service.run_paper_reward_candidates(max_candidates=5, per_order_notional=1.0)
    assert run["candidate_count"] == 5
    assert run["submitted_count"] == 5
    assert len(service.store.candidates) == 5

    settled = service.settle_paper_reward_candidates(limit=5)
    assert settled["updated_count"] == 5
    assert settled["bandit_updated"] is True
    assert service.store.bandit_state["arms"]
    assert all(candidate["status"] == "settled" for candidate in service.store.candidates.values())

    leaderboard = service.paper_reward_leaderboard(limit=5)
    assert leaderboard["candidate_count"] == 5
    assert leaderboard["leaderboard"][0]["settled_count"] >= 1
    assert leaderboard["leaderboard"][0]["bandit_pulls"] >= 1
