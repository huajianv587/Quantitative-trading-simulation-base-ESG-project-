from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gateway.quant.models import BrokerDescriptor


class BrokerAdapter(ABC):
    broker_id: str = ""
    label: str = ""
    channel: str = "paper"
    live_supported: bool = False
    paper_supported: bool = False
    capabilities: list[str] = []
    auth_hints: list[str] = []

    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def connection_status(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_account(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_clock(self) -> dict[str, Any]:
        raise RuntimeError(f"{self.label} does not expose a market clock helper.")

    @abstractmethod
    def list_orders(self, status: str = "all", limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_asset(self, symbol: str) -> dict[str, Any]:
        raise RuntimeError(f"{self.label} does not expose asset metadata.")

    @abstractmethod
    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        raise RuntimeError(f"{self.label} does not support order cancellation.")

    def descriptor(self) -> BrokerDescriptor:
        return BrokerDescriptor(
            broker_id=self.broker_id,
            label=self.label,
            channel=self.channel,
            configured=self.configured(),
            live_supported=self.live_supported,
            paper_supported=self.paper_supported,
            capabilities=list(self.capabilities),
            auth_hints=list(self.auth_hints),
            metadata=self.connection_status(),
        )


class PlaceholderBrokerAdapter(BrokerAdapter):
    metadata: dict[str, Any]

    def __init__(self, metadata: dict[str, Any] | None = None) -> None:
        self.metadata = metadata or {}

    def configured(self) -> bool:
        return bool(self.metadata.get("configured"))

    def connection_status(self) -> dict[str, Any]:
        return {
            "broker": self.broker_id,
            "configured": self.configured(),
            "implementation_status": self.metadata.get("implementation_status", "scaffolded"),
            **self.metadata,
        }

    def get_account(self) -> dict[str, Any]:
        raise RuntimeError(f"{self.label} is scaffolded but not yet enabled in this runtime.")

    def list_orders(self, status: str = "all", limit: int = 20) -> list[dict[str, Any]]:
        raise RuntimeError(f"{self.label} is scaffolded but not yet enabled in this runtime.")

    def list_positions(self) -> list[dict[str, Any]]:
        raise RuntimeError(f"{self.label} is scaffolded but not yet enabled in this runtime.")

    def get_order(self, order_id: str) -> dict[str, Any]:
        raise RuntimeError(f"{self.label} is scaffolded but not yet enabled in this runtime.")

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(f"{self.label} is scaffolded but not yet enabled in this runtime.")
