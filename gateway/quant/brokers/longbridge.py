from __future__ import annotations

from gateway.config import settings
from gateway.quant.brokers.base import PlaceholderBrokerAdapter


class LongbridgeBrokerAdapter(PlaceholderBrokerAdapter):
    broker_id = "longbridge"
    label = "Longbridge OpenAPI"
    channel = "paper/live"
    live_supported = True
    paper_supported = True
    capabilities = [
        "token_auth",
        "account_snapshot",
        "orders",
        "positions",
        "cancel_order",
    ]
    auth_hints = [
        "LONGBRIDGE_APP_KEY",
        "LONGBRIDGE_APP_SECRET",
        "LONGBRIDGE_ACCESS_TOKEN",
    ]

    def __init__(self) -> None:
        super().__init__(
            {
                "configured": bool(
                    getattr(settings, "LONGBRIDGE_APP_KEY", "")
                    and getattr(settings, "LONGBRIDGE_APP_SECRET", "")
                    and getattr(settings, "LONGBRIDGE_ACCESS_TOKEN", "")
                ),
                "region": getattr(settings, "LONGBRIDGE_REGION", "us"),
                "paper_mode": bool(getattr(settings, "LONGBRIDGE_PAPER_MODE", True)),
                "implementation_status": "scaffolded",
            }
        )
