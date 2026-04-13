from __future__ import annotations

from typing import Any, Callable

from gateway.quant.brokers.alpaca import AlpacaBrokerAdapter
from gateway.quant.brokers.ibkr import IbkrBrokerAdapter
from gateway.quant.brokers.longbridge import LongbridgeBrokerAdapter
from gateway.quant.brokers.tiger import TigerBrokerAdapter


class BrokerRegistry:
    def __init__(self, get_alpaca_client: Callable[[], Any]) -> None:
        self._brokers = {
            "alpaca": AlpacaBrokerAdapter(get_alpaca_client),
            "ibkr": IbkrBrokerAdapter(),
            "tiger": TigerBrokerAdapter(),
            "longbridge": LongbridgeBrokerAdapter(),
        }

    def list_brokers(self):
        return [adapter.descriptor() for adapter in self._brokers.values()]

    def get(self, broker_id: str | None):
        normalized = (broker_id or "alpaca").strip().lower()
        if normalized not in self._brokers:
            raise KeyError(f"Unsupported broker: {broker_id}")
        return self._brokers[normalized]

    def has(self, broker_id: str | None) -> bool:
        try:
            self.get(broker_id)
        except KeyError:
            return False
        return True
