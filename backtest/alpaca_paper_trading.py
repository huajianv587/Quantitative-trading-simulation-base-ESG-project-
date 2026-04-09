from __future__ import annotations

from typing import Any

from gateway.quant.alpaca import AlpacaPaperClient


def run_module(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    client = AlpacaPaperClient()
    action = str(payload.get("action") or "status").strip().lower()

    result: dict[str, Any] = {
        "module": "alpaca_paper_trading",
        "configured": client.configured(),
        "broker_connection": client.connection_status(),
        "requested_action": action,
    }

    if not client.configured():
        result["status"] = "not_configured"
        result["message"] = "Missing Alpaca paper credentials."
        return result

    if action == "account":
        result["status"] = "ok"
        result["account"] = client.get_account()
        result["clock"] = client.get_clock()
        return result

    if action == "orders":
        result["status"] = "ok"
        result["orders"] = client.list_orders(
            status=str(payload.get("status") or "all"),
            limit=int(payload.get("limit") or 20),
        )
        return result

    if action == "positions":
        result["status"] = "ok"
        result["positions"] = client.list_positions()
        return result

    if action == "submit":
        order_payload = dict(payload.get("order") or {})
        if not order_payload:
            return {
                **result,
                "status": "invalid_request",
                "message": "Missing payload['order'] for submit action.",
            }
        result["status"] = "ok"
        result["order"] = client.submit_order(order_payload)
        return result

    result["status"] = "ready"
    result["message"] = "Supported actions: status, account, orders, positions, submit."
    return result
