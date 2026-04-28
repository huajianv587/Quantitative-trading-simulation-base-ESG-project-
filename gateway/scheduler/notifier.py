from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from gateway.config import settings
from gateway.db.supabase_client import get_client
from gateway.utils.email_delivery import send_email_message
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class Notifier:
    """Multi-channel notification sender for report and event pushes."""

    def __init__(self):
        self.db = get_client()
        self.local_notifications: list[dict[str, Any]] = []

    def generate_notification_content(self, event: dict, risk_score: dict, user_id: str) -> dict:
        severity = str(risk_score.get("risk_level") or "medium").lower()
        title = f"ESG Alert: {event.get('title', 'New ESG Event')}"
        content = f"""
Event: {event.get('title', 'N/A')}
Company: {event.get('company', 'N/A')}
Type: {event.get('event_type', 'N/A')}
Risk Level: {severity.upper()}
Risk Score: {risk_score.get('score', 0)}/100

Description:
{event.get('description', 'N/A')}

Key Metrics:
{self._format_metrics(event.get('key_metrics', {}))}

Risk Assessment:
{risk_score.get('reasoning', 'N/A')}

Recommendation:
{risk_score.get('recommendation', 'N/A')}
        """
        return {
            "title": title,
            "content": content.strip(),
            "severity": severity,
            "action_url": f"/events/{event.get('id')}",
        }

    @staticmethod
    def _format_metrics(metrics: dict) -> str:
        if not metrics:
            return "No metrics available"
        return "\n".join([f"- {key}: {value}" for key, value in metrics.items()])

    def send_email_notification(self, user_email: str, notification: dict) -> bool:
        try:
            html_content = f"""
            <html>
              <body>
                <h2>{notification['title']}</h2>
                <pre>{notification['content']}</pre>
                <a href="{notification['action_url']}">View Details</a>
              </body>
            </html>
            """
            result = send_email_message(
                recipient=user_email,
                subject=notification["title"],
                text_body=notification["content"],
                html_body=html_content,
                sender=settings.EMAIL_FROM or settings.SMTP_USER or "noreply@esg-system.com",
            )
            if result.get("ok"):
                logger.info(f"[Notifier] Email sent to {user_email}")
                return True
            logger.error(f"[Notifier] Email send failed for {user_email}: {result.get('detail')}")
            return False
        except Exception as exc:
            logger.error(f"[Notifier] Failed to send email to {user_email}: {exc}")
            return False

    def send_telegram_notification(self, notification: dict) -> bool:
        token = str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        chat_id = str(getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
        if not token or not chat_id:
            logger.warning("[Notifier] Telegram is not configured")
            return False
        text = f"{notification['title']}\n\n{notification['content']}\n\n{notification.get('action_url', '')}"[:3500]
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                timeout=max(1, int(getattr(settings, "ALERT_NOTIFIER_TIMEOUT_SECONDS", 5) or 5)),
            )
            if response.ok:
                logger.info("[Notifier] Telegram notification sent")
                return True
            logger.error(f"[Notifier] Telegram send failed: {response.status_code} {response.text[:200]}")
            return False
        except Exception as exc:
            logger.error(f"[Notifier] Telegram send failed: {exc}")
            return False

    def send_in_app_notification(self, user_id: str, notification: dict) -> bool:
        try:
            self.db.table("in_app_notifications").insert(
                {
                    "user_id": user_id,
                    "title": notification["title"],
                    "content": notification["content"],
                    "severity": notification["severity"],
                    "action_url": notification["action_url"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "read_at": None,
                }
            ).execute()
            logger.info(f"[Notifier] In-app notification saved for user {user_id}")
            return True
        except Exception as exc:
            logger.error(f"[Notifier] Failed to save in-app notification: {exc}")
            return False

    def send_webhook_notification(self, webhook_url: str, notification: dict, event: dict) -> bool:
        try:
            response = requests.post(
                webhook_url,
                json={
                    "notification": notification,
                    "event": {
                        "id": event.get("id"),
                        "title": event.get("title"),
                        "company": event.get("company"),
                        "event_type": event.get("event_type"),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                timeout=5,
            )
            if response.status_code == 200:
                logger.info(f"[Notifier] Webhook notification sent to {webhook_url}")
                return True
            logger.warning(f"[Notifier] Webhook returned {response.status_code}")
            return False
        except Exception as exc:
            logger.error(f"[Notifier] Failed to send webhook: {exc}")
            return False

    def send_notification(
        self,
        user_id: str,
        report_id: str,
        title: str,
        content: str,
        severity: str = "medium",
        channels: list[str] | None = None,
        template_id: str | None = None,
    ) -> dict:
        channels = channels or ["in_app"]
        notification = {
            "title": title,
            "content": content,
            "severity": severity,
            "action_url": f"/admin/reports/{report_id}" if report_id else "",
            "template_id": template_id,
        }
        pref = self._load_user_preferences(user_id)
        sent_channels: list[str] = []
        for channel in channels:
            normalized = str(channel or "").strip().lower()
            success = False
            if normalized == "email":
                user_email = (pref or {}).get("email") or settings.SMTP_USER
                if user_email:
                    success = self.send_email_notification(user_email, notification)
            elif normalized == "telegram":
                success = self.send_telegram_notification(notification)
            elif normalized == "in_app":
                success = self.send_in_app_notification(user_id, notification)
            elif normalized == "webhook":
                webhook_url = (pref or {}).get("webhook_url")
                if webhook_url:
                    success = self.send_webhook_notification(webhook_url, notification, {"id": report_id, "title": title})

            if success:
                sent_channels.append(normalized)
                self.save_notification_log(report_id, user_id, normalized, "sent")
            else:
                self.save_notification_log(report_id, user_id, normalized, "failed")

        if not sent_channels:
            local_copy = {
                "user_id": user_id,
                "report_id": report_id,
                **notification,
                "channels": channels,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.local_notifications.append(local_copy)
            logger.info(f"[Notifier] Stored local fallback notification for {user_id}")

        return {
            "user_id": user_id,
            "report_id": report_id,
            "requested_channels": channels,
            "sent_channels": sent_channels,
            "stored_locally": not sent_channels,
        }

    def send_notifications(self, event_id: str, user_ids: list[str]) -> dict:
        if not user_ids:
            return {"total": 0, "sent": 0, "failed": 0, "by_channel": {}}
        try:
            event_response = self.db.table("extracted_events").select("*").eq("id", event_id).execute()
            if not event_response.data:
                logger.warning(f"[Notifier] Event {event_id} not found")
                return {"total": 0, "sent": 0, "failed": 0, "by_channel": {}}
            event = event_response.data[0]
            score_response = self.db.table("risk_scores").select("*").eq("event_id", event_id).execute()
            risk_score = score_response.data[0] if score_response.data else {}
            notification = self.generate_notification_content(event, risk_score, "")
            sent_count = 0
            by_channel = {"email": 0, "in_app": 0, "webhook": 0, "telegram": 0}
            for user_id in user_ids:
                preferences = self._load_user_preferences(user_id)
                if not preferences:
                    logger.warning(f"[Notifier] No preferences found for user {user_id}")
                    continue
                channels = preferences.get("notification_channels", ["in_app"])
                result = self.send_notification(
                    user_id=user_id,
                    report_id=event_id,
                    title=notification["title"],
                    content=notification["content"],
                    severity=notification["severity"],
                    channels=channels,
                )
                for channel in result.get("sent_channels", []):
                    by_channel[channel] = by_channel.get(channel, 0) + 1
                    sent_count += 1
            return {
                "total": len(user_ids),
                "sent": sent_count,
                "failed": max(len(user_ids) - sent_count, 0),
                "by_channel": by_channel,
            }
        except Exception as exc:
            logger.error(f"[Notifier] Batch notification failed: {exc}")
            return {"total": len(user_ids), "sent": 0, "failed": len(user_ids), "by_channel": {}}

    def _load_user_preferences(self, user_id: str) -> dict[str, Any] | None:
        try:
            response = self.db.table("user_preferences").select("*").eq("user_id", user_id).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as exc:
            logger.warning(f"[Notifier] Preference lookup failed for {user_id}: {exc}")
            return None

    def save_notification_log(self, event_id: str, user_id: str, channel: str, status: str) -> bool:
        try:
            self.db.table("notification_logs").insert(
                {
                    "event_id": event_id,
                    "user_id": user_id,
                    "channel": channel,
                    "status": status,
                    "sent_at": datetime.now(timezone.utc).isoformat() if status == "sent" else None,
                }
            ).execute()
            return True
        except Exception as exc:
            logger.error(f"[Notifier] Failed to save log: {exc}")
            return False


_notifier = None


def get_notifier() -> Notifier:
    """Return the process-wide notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier
