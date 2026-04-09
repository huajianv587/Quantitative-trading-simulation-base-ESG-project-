from __future__ import annotations

from gateway.quant.service import QuantSystemService


class _FakeAlpaca:
    def connection_status(self):
        return {
            "configured": True,
            "broker": "alpaca-paper",
            "base_url": "https://paper-api.alpaca.markets",
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
            "client_order_id": f"client-{symbol.lower()}",
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


def test_quant_execution_plan_can_submit_mock_alpaca_orders(monkeypatch):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    service.alpaca = _FakeAlpaca()

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


def test_quant_execution_broker_views_expose_account_orders_and_positions():
    service = QuantSystemService()
    service.alpaca = _FakeAlpaca()

    account = service.get_execution_account()
    orders = service.list_execution_orders()
    positions = service.list_execution_positions()

    assert account["connected"] is True
    assert account["account"]["status"] == "ACTIVE"
    assert orders["orders"][0]["symbol"] == "AAPL"
    assert positions["positions"][0]["symbol"] == "AAPL"
    assert any("Market is currently closed" in warning for warning in account["warnings"])


def test_quant_execution_plan_blocks_when_buying_power_is_below_requested_notional(monkeypatch):
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_TEST_ORDERS", 2)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
    monkeypatch.setattr("gateway.quant.service.settings.ALPACA_MAX_ORDER_NOTIONAL", 10.0)

    service = QuantSystemService()
    service.alpaca = _LowBuyingPowerAlpaca()

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
