from __future__ import annotations

from gateway.config import settings
from gateway.quant.brokers.base import PlaceholderBrokerAdapter


class TigerBrokerAdapter(PlaceholderBrokerAdapter):
    broker_id = "tiger"
    label = "Tiger OpenAPI"
    channel = "paper/live"
    live_supported = True
    paper_supported = True
    capabilities = [
        "rsa_signature_auth",
        "account_snapshot",
        "orders",
        "positions",
        "cancel_order",
    ]
    auth_hints = [
        "TIGER_ID",
        "TIGER_ACCOUNT",
        "TIGER_PRIVATE_KEY_PATH",
        "TIGER_ACCESS_TOKEN",
    ]

    def __init__(self) -> None:
        super().__init__(
            {
                "configured": bool(
                    getattr(settings, "TIGER_ID", "")
                    and getattr(settings, "TIGER_ACCOUNT", "")
                    and getattr(settings, "TIGER_PRIVATE_KEY_PATH", "")
                    and getattr(settings, "TIGER_ACCESS_TOKEN", "")
                ),
                "account": getattr(settings, "TIGER_ACCOUNT", ""),
                "region": getattr(settings, "TIGER_REGION", "US"),
                "paper_mode": bool(getattr(settings, "TIGER_PAPER_MODE", True)),
                "implementation_status": "scaffolded",
            }
        )
