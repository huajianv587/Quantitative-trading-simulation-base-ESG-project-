from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from gateway.quant.market_data import MarketBarsResult
from gateway.quant.service import QuantSystemService
from gateway.quant.signals import MovingAverageCrossSignalEngine


class _FakeAlpaca:
    def connection_status(self, mode=None):
        runtime_mode = "live" if str(mode or "").lower() == "live" else "paper"
        return {
            "configured": runtime_mode == "paper",
            "broker": "alpaca",
            "mode": runtime_mode,
            "requested_mode": runtime_mode,
            "effective_mode": "paper",
            "base_url": "https://paper-api.alpaca.markets" if runtime_mode == "paper" else "https://api.alpaca.markets",
            "paper_base_url": "https://paper-api.alpaca.markets",
            "live_base_url": "https://api.alpaca.markets",
            "paper_configured": True,
            "live_configured": False,
            "live_available": False,
        }

    def get_account(self):
        return {
            "id": "acct-001",
            "status": "ACTIVE",
            "currency": "USD",
            "buying_power": "25000.00",
            "cash": "25000.00",
            "equity": "25000.00",
            "last_equity": "25000.00",
            "trading_blocked": False,
            "account_blocked": False,
            "transfers_blocked": False,
            "shorting_enabled": True,
            "pattern_day_trader": False,
        }

    def get_clock(self):
        return {
            "is_open": False,
            "timestamp": "2026-04-09T12:00:00Z",
            "next_open": "2026-04-10T13:30:00Z",
            "next_close": "2026-04-10T20:00:00Z",
        }

    def get_asset(self, symbol: str):
        return {
            "symbol": symbol,
            "tradable": True,
            "fractionable": True,
        }

    def submit_order(self, payload):
        return {
            "id": f"ord-{payload['symbol'].lower()}",
            "client_order_id": payload["client_order_id"],
            "symbol": payload["symbol"],
            "side": payload["side"],
            "type": payload["type"],
            "time_in_force": payload["time_in_force"],
            "status": "accepted",
            "qty": payload.get("qty"),
            "notional": payload.get("notional"),
            "filled_qty": "0",
            "filled_avg_price": None,
            "created_at": "2026-04-09T12:01:00Z",
        }

    def get_order(self, order_id: str):
        symbol = order_id.split("-")[-1].upper()
        return {
            "id": order_id,
            "client_order_id": f"execution-20260409000000-{symbol.lower()}-1",
            "symbol": symbol,
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "status": "new",
            "qty": None,
            "notional": "1.25",
            "filled_qty": "0",
            "filled_avg_price": None,
            "submitted_at": "2026-04-09T12:01:01Z",
        }

    def list_orders(self, status: str = "all", limit: int = 20):
        return [
            {
                "id": "ord-aapl",
                "client_order_id": "client-aapl",
                "symbol": "AAPL",
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
                "status": "filled",
                "qty": None,
                "notional": "1.00",
                "filled_qty": "0.005",
                "filled_avg_price": "201.11",
                "submitted_at": "2026-04-09T12:03:00Z",
            }
        ]

    def cancel_order(self, order_id: str):
        return {
            "id": order_id,
            "status": "canceled",
        }

    def list_positions(self):
        return [
            {
                "symbol": "AAPL",
                "qty": "0.005",
                "market_value": "1.01",
                "cost_basis": "1.00",
                "side": "long",
                "avg_entry_price": "201.11",
                "unrealized_pl": "0.01",
                "unrealized_plpc": "0.01",
            }
        ]


class _LowBuyingPowerAlpaca(_FakeAlpaca):
    def get_account(self):
        payload = super().get_account()
        payload["buying_power"] = "0.50"
        payload["cash"] = "-10.00"
        return payload


class _BullishMarketData:
    def get_daily_bars(self, symbol: str, limit: int = 180, force_refresh: bool = False):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        price = 100.0
        closes = []
        for index in range(120):
            price += 0.45
            closes.append(
                {
                    "timestamp": base + timedelta(days=index),
                    "open": price - 0.2,
                    "high": price + 0.4,
                    "low": price - 0.5,
                    "close": price,
                    "volume": 1_000_000 + index,
                    "trade_count": 1000 + index,
                    "vwap": price,
                }
            )
        return MarketBarsResult(
            symbol=symbol,
            provider="alpaca",
            timeframe="1Day",
            cache_hit=False,
            bars=pd.DataFrame(closes),
            cache_path="storage/quant/market_data/bars.sqlite3",
        )


def _configure_bullish_market_data(service: QuantSystemService) -> None:
    service.market_data = _BullishMarketData()
    service.signal_engine = MovingAverageCrossSignalEngine(service.market_data)


def _configure_test_storage(service: QuantSystemService, tmp_path) -> None:
    service.storage.base_dir = tmp_path


def test_quant_execution_plan_can_submit_mock_alpaca_orders(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)

    payload = service.create_execution_plan(
        universe_symbols=["AAPL", "MSFT", "TSLA"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )

    assert payload["submitted"] is True
    assert payload["broker_status"] == "submitted"
    assert payload["account_snapshot"]["buying_power"] == "25000.00"
    assert len(payload["submitted_orders"]) == 1
    assert payload["submitted_orders"][0]["symbol"] in {"AAPL", "MSFT", "TSLA"}
    assert payload["orders"][0]["status"] == "new"
    assert payload["orders"][0]["client_order_id"]


def test_quant_execution_broker_views_expose_account_orders_and_positions(tmp_path):
    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()

    account = service.get_execution_account()
    orders = service.list_execution_orders()
    positions = service.list_execution_positions()

    assert account["connected"] is True
    assert account["requested_mode"] == "paper"
    assert account["effective_mode"] == "paper"
    assert account["paper_ready"] is True
    assert account["live_available"] is False
    assert account["account"]["status"] == "ACTIVE"
    assert orders["orders"][0]["symbol"] == "AAPL"
    assert orders["requested_mode"] == "paper"
    assert positions["positions"][0]["symbol"] == "AAPL"
    assert positions["effective_mode"] == "paper"
    assert any("Market is currently closed" in warning for warning in account["warnings"])


def test_quant_execution_account_marks_live_mode_as_blocked_until_ready(tmp_path):
    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()

    account = service.get_execution_account(mode="live")

    assert account["connected"] is False
    assert account["requested_mode"] == "live"
    assert account["effective_mode"] == "paper"
    assert account["live_ready"] is False
    assert account["live_available"] is False
    assert account["block_reason"] == "live_credentials_missing"


def test_quant_execution_plan_blocks_when_buying_power_is_below_requested_notional(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _LowBuyingPowerAlpaca()
    _configure_bullish_market_data(service)

    payload = service.create_execution_plan(
        universe_symbols=["AAPL", "MSFT"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )

    assert payload["submitted"] is False
    assert payload["broker_status"] == "insufficient_buying_power"
    assert any("Buying power" in warning for warning in payload["warnings"])
    assert any("Account cash is negative" in warning for warning in payload["warnings"])


def test_quant_broker_inventory_and_validation_report_are_available(tmp_path):
    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)

    brokers = service.list_execution_brokers()
    validation = service.run_alpha_validation(
        strategy_name="ESG Multi-Factor Long-Only",
        universe_symbols=["AAPL", "MSFT", "TSLA"],
    )

    assert any(item["broker_id"] == "alpaca" for item in brokers)
    assert validation["validation_id"].startswith("validation-")
    assert validation["walk_forward_windows"]
    assert validation["robustness_score"] >= 0


def test_quant_execution_journal_supports_cancel_and_retry(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)

    payload = service.create_execution_plan(
        universe_symbols=["AAPL", "MSFT"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )
    order_id = payload["orders"][0]["client_order_id"]

    canceled = service.cancel_execution_order(
        order_id=order_id,
        broker="alpaca",
        execution_id=payload["execution_id"],
    )
    retried = service.retry_execution_order(
        order_id=order_id,
        broker="alpaca",
        execution_id=payload["execution_id"],
        per_order_notional=1.25,
    )

    assert canceled["journal_record"]["cancel_requested"] is True
    assert retried["journal_record"]["retry_count"] == 1
    assert retried["state_machine"]["state"] in {"routed", "cancel_requested", "ready_to_route"}


def test_quant_execution_journal_can_sync_broker_state(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)

    payload = service.create_execution_plan(
        universe_symbols=["AAPL", "MSFT"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )
    synced = service.sync_execution_journal(payload["execution_id"], broker="alpaca")

    assert synced["records_synced"] == 1
    assert synced["state_machine"]["state"] == "routed"
    assert payload["orders"][0]["client_order_id"] in synced["cancelable_order_ids"]


def test_quant_execution_kill_switch_blocks_submission(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)
    service.set_execution_kill_switch(enabled=True, reason="unit-test kill switch")

    payload = service.create_execution_plan(
        universe_symbols=["AAPL", "MSFT"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )

    assert payload["submitted"] is False
    assert payload["broker_status"] == "kill_switch_engaged"
    assert payload["controls"]["kill_switch_enabled"] is True
    assert payload["state_machine"]["state"] == "blocked"
    assert any("kill switch" in warning.lower() for warning in payload["warnings"])


def test_quant_execution_duplicate_guard_suppresses_second_batch(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)
    monkeypatch.setattr("gateway.quant.service.settings.EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES", 120)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)

    first = service.create_execution_plan(
        universe_symbols=["AAPL"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )
    second = service.create_execution_plan(
        universe_symbols=["AAPL"],
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )

    assert first["submitted"] is True
    assert second["submitted"] is False
    assert second["broker_status"] == "suppressed"
    assert second["orders"][0]["status"] == "suppressed_duplicate"
    assert second["state_machine"]["state"] == "suppressed"


def test_quant_execution_plan_blocks_live_submit_without_live_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    _configure_test_storage(service, tmp_path)
    service.alpaca = _FakeAlpaca()
    _configure_bullish_market_data(service)

    payload = service.create_execution_plan(
        universe_symbols=["AAPL"],
        mode="live",
        submit_orders=True,
        max_orders=1,
        per_order_notional=1.25,
    )

    assert payload["submitted"] is False
    assert payload["requested_mode"] == "live"
    assert payload["effective_mode"] == "paper"
    assert payload["live_ready"] is False
    assert payload["live_available"] is False
    assert payload["block_reason"] == "live_credentials_missing"
    assert "Live mode was selected" in " ".join(payload["warnings"])
