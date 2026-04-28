from __future__ import annotations

from typing import Any

import requests

from gateway.config import settings
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class AlpacaPaperClient:
    def __init__(self) -> None:
        self.paper_key_id = getattr(settings, "ALPACA_API_KEY", "")
        self.paper_secret_key = getattr(settings, "ALPACA_API_SECRET", "")
        self.live_key_id = getattr(settings, "ALPACA_LIVE_API_KEY", "")
        self.live_secret_key = getattr(settings, "ALPACA_LIVE_API_SECRET", "")
        self.paper_base_url = (
            getattr(settings, "ALPACA_PAPER_BASE_URL", "")
            or "https://paper-api.alpaca.markets"
        ).rstrip("/")
        self.live_base_url = (
            getattr(settings, "ALPACA_LIVE_BASE_URL", "")
            or "https://api.alpaca.markets"
        ).rstrip("/")
        self.timeout = int(getattr(settings, "ALPACA_API_TIMEOUT", 20) or 20)
        self.runtime_mode = "paper"

    def _normalize_mode(self, mode: str | None = None) -> str:
        return "live" if str(mode or self.runtime_mode or "").strip().lower() == "live" else "paper"

    def _credentials_for_mode(self, mode: str | None = None) -> tuple[str, str]:
        normalized = self._normalize_mode(mode)
        if normalized == "live":
            return self.live_key_id, self.live_secret_key
        return self.paper_key_id, self.paper_secret_key

    def configured(self, mode: str | None = None) -> bool:
        key_id, secret_key = self._credentials_for_mode(mode)
        base_url = self._base_url_for_mode(mode)
        return bool(key_id and secret_key and base_url)

    def set_runtime_mode(self, mode: str | None) -> str:
        normalized = self._normalize_mode(mode)
        self.runtime_mode = normalized
        return self.runtime_mode

    def _base_url_for_mode(self, mode: str | None = None) -> str:
        normalized = self._normalize_mode(mode)
        return self.live_base_url if normalized == "live" else self.paper_base_url

    def connection_status(self, mode: str | None = None) -> dict[str, Any]:
        normalized = self._normalize_mode(mode)
        paper_configured = self.configured("paper")
        live_configured = self.configured("live")
        return {
            "configured": self.configured(normalized),
            "broker": "alpaca",
            "mode": normalized,
            "requested_mode": normalized,
            "effective_mode": normalized if normalized == "paper" or live_configured else "paper",
            "base_url": self._base_url_for_mode(normalized),
            "paper_base_url": self.paper_base_url,
            "live_base_url": self.live_base_url,
            "paper_configured": paper_configured,
            "live_configured": live_configured,
            "live_available": live_configured,
        }

    def get_account(self) -> dict[str, Any]:
        return self._request("GET", "/v2/account")

    def get_clock(self) -> dict[str, Any]:
        return self._request("GET", "/v2/clock")

    def get_asset(self, symbol: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/assets/{symbol.upper().strip()}")

    def list_orders(
        self,
        status: str = "all",
        limit: int = 20,
        *,
        after: str | None = None,
        until: str | None = None,
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        params = {
            "status": status,
            "limit": max(1, min(int(limit), 500)),
            "direction": direction,
            "nested": "false",
        }
        if after:
            params["after"] = after
        if until:
            params["until"] = until
        payload = self._request("GET", "/v2/orders", params=params)
        return payload if isinstance(payload, list) else []

    def list_positions(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/v2/positions")
        return payload if isinstance(payload, list) else []

    def list_account_activities(
        self,
        *,
        activity_types: str = "FILL,CSD,CSW",
        after: str | None = None,
        until: str | None = None,
        direction: str = "desc",
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        params = {
            "activity_types": activity_types,
            "direction": direction,
            "page_size": max(1, min(int(page_size), 100)),
        }
        if after:
            params["after"] = after
        if until:
            params["until"] = until
        payload = self._request("GET", "/v2/account/activities", params=params)
        return payload if isinstance(payload, list) else []

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v2/orders", json=payload)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/orders/{order_id}")

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        payload = self._request("DELETE", f"/v2/orders/{order_id}")
        if isinstance(payload, dict) and payload:
            return payload
        return {"id": order_id, "status": "cancel_requested"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        mode: str | None = None,
    ) -> Any:
        normalized = self._normalize_mode(mode)
        if not self.configured(normalized):
            scope = "live" if normalized == "live" else "paper"
            raise RuntimeError(f"Alpaca {scope} trading credentials are not configured")

        key_id, secret_key = self._credentials_for_mode(normalized)

        url = f"{self._base_url_for_mode(normalized)}{path}"
        response = requests.request(
            method=method.upper(),
            url=url,
            headers={
                "APCA-API-KEY-ID": key_id,
                "APCA-API-SECRET-KEY": secret_key,
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
