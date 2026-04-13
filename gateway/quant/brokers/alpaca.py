from __future__ import annotations

from typing import Any, Callable

from gateway.quant.brokers.base import BrokerAdapter


class AlpacaBrokerAdapter(BrokerAdapter):
    broker_id = "alpaca"
    label = "Alpaca"
    channel = "paper/live"
    live_supported = True
    paper_supported = True
    capabilities = [
        "paper_trading",
        "market_orders",
        "limit_orders",
        "fractional_notional",
        "cancel_order",
        "order_status",
        "positions",
        "account_snapshot",
    ]
    auth_hints = [
        "ALPACA_API_KEY",
        "ALPACA_API_SECRET",
        "ALPACA_PAPER_BASE_URL",
    ]

    def __init__(self, get_client: Callable[[], Any]) -> None:
        self._get_client = get_client

    @property
    def client(self) -> Any:
        return self._get_client()

    def configured(self) -> bool:
        if hasattr(self.client, "configured"):
            return bool(self.client.configured())
        status = self.connection_status()
        return bool(status.get("configured"))

    def connection_status(self) -> dict[str, Any]:
        status = dict(self.client.connection_status())
        status["broker"] = self.broker_id
        return status

    def get_account(self) -> dict[str, Any]:
        return self.client.get_account()

    def get_clock(self) -> dict[str, Any]:
        return self.client.get_clock()

    def list_orders(self, status: str = "all", limit: int = 20) -> list[dict[str, Any]]:
        return self.client.list_orders(status=status, limit=limit)

    def list_positions(self) -> list[dict[str, Any]]:
        return self.client.list_positions()

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self.client.get_order(order_id)

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return self.client.get_asset(symbol)

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.submit_order(payload)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self.client.cancel_order(order_id)
