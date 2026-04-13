from __future__ import annotations

from gateway.config import settings
from gateway.quant.brokers.base import PlaceholderBrokerAdapter


class IbkrBrokerAdapter(PlaceholderBrokerAdapter):
    broker_id = "ibkr"
    label = "Interactive Brokers"
    channel = "live"
    live_supported = True
    paper_supported = True
    capabilities = [
        "gateway_session",
        "account_snapshot",
        "orders",
        "positions",
        "cancel_order",
    ]
    auth_hints = [
        "IBKR_GATEWAY_URL",
        "IBKR_ACCOUNT_ID",
        "IBKR_USERNAME",
        "IBKR_PASSWORD",
    ]

    def __init__(self) -> None:
        super().__init__(
            {
                "configured": bool(getattr(settings, "IBKR_GATEWAY_URL", "") and getattr(settings, "IBKR_ACCOUNT_ID", "")),
                "gateway_url": getattr(settings, "IBKR_GATEWAY_URL", ""),
                "account_id": getattr(settings, "IBKR_ACCOUNT_ID", ""),
                "paper_mode": bool(getattr(settings, "IBKR_PAPER_MODE", True)),
                "implementation_status": "scaffolded",
            }
        )
