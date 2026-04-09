from __future__ import annotations

from typing import Any

import requests

from gateway.config import settings
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class AlpacaPaperClient:
    def __init__(self) -> None:
        self.key_id = getattr(settings, "ALPACA_API_KEY", "")
        self.secret_key = getattr(settings, "ALPACA_API_SECRET", "")
        self.base_url = (
            getattr(settings, "ALPACA_PAPER_BASE_URL", "")
            or "https://paper-api.alpaca.markets"
        ).rstrip("/")
        self.timeout = int(getattr(settings, "ALPACA_API_TIMEOUT", 20) or 20)

    def configured(self) -> bool:
        return bool(self.key_id and self.secret_key and self.base_url)

    def connection_status(self) -> dict[str, Any]:
        return {
            "configured": self.configured(),
            "broker": "alpaca-paper",
            "base_url": self.base_url,
        }

    def get_account(self) -> dict[str, Any]:
        return self._request("GET", "/v2/account")

    def get_clock(self) -> dict[str, Any]:
        return self._request("GET", "/v2/clock")

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/assets/{symbol.upper().strip()}")

    def list_orders(self, status: str = "all", limit: int = 20) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/v2/orders",
            params={
                "status": status,
                "limit": max(1, min(int(limit), 100)),
                "direction": "desc",
                "nested": "false",
            },
        )
        return payload if isinstance(payload, list) else []

    def list_positions(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/v2/positions")
        return payload if isinstance(payload, list) else []

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v2/orders", json=payload)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/orders/{order_id}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if not self.configured():
            raise RuntimeError("Alpaca paper trading credentials are not configured")

        url = f"{self.base_url}{path}"
        response = requests.request(
            method=method.upper(),
            url=url,
            headers={
                "APCA-API-KEY-ID": self.key_id,
                "APCA-API-SECRET-KEY": self.secret_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            params=params,
            json=json,
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            detail = self._extract_error_message(response)
            raise RuntimeError(f"Alpaca API {response.status_code}: {detail}")

        if not response.content:
            return {}

        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(f"Alpaca API returned non-JSON payload: {exc}") from exc

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return response.text.strip() or "unknown error"

        if isinstance(payload, dict):
            return str(
                payload.get("message")
                or payload.get("error")
                or payload.get("detail")
                or payload
            )
        return str(payload)
