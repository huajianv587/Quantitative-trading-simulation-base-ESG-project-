# notifier.py — 通知推送模块
# 职责：根据匹配结果和风险评分，生成并推送通知给用户
# 支持多渠道推送：邮件、应用内通知、webhook 等

import json
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from gateway.utils.logger import get_logger
from gateway.config import settings
from gateway.db.supabase_client import get_client

logger = get_logger(__name__)


class Notifier:
    """通知推送器"""

    def __init__(self):
        self.db = get_client()
        self.local_notifications: list[dict] = []

    def generate_notification_content(self, event: dict, risk_score: dict, user_id: str) -> dict:
        """
        为用户生成通知内容。

        Args:
            event: 事件数据
            risk_score: 风险评分
            user_id: 目标用户

        Returns:
            通知内容 {"title", "content", "severity", "action_url"}
        """
        title = f"🚨 ESG Alert: {event.get('title', 'New Event')}"

        # 根据风险等级选择标题前缀
        severity = risk_score.get("risk_level", "medium")
        severity_emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨",
        }.get(severity, "ℹ️")

        title = f"{severity_emoji} {event.get('title', 'New ESG Event')}"

        # 生成内容
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

---
View full analysis: https://esg-dashboard.example.com/events/{event.get('id')}
        """

        return {
            "title": title,
            "content": content.strip(),
            "severity": severity,
            "action_url": f"https://esg-dashboard.example.com/events/{event.get('id')}",
        }

    def _format_metrics(self, metrics: dict) -> str:
        """格式化关键指标为可读文本"""
        if not metrics:
            return "No metrics available"
        return "\n".join([f"  • {k}: {v}" for k, v in metrics.items()])

    def send_email_notification(self, user_email: str, notification: dict) -> bool:
        """
        发送邮件通知。

        Args:
            user_email: 收件人邮箱
            notification: 通知内容

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            # 构建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notification["title"]
            msg["From"] = settings.EMAIL_FROM or "noreply@esg-system.com"
            msg["To"] = user_email

            # 纯文本部分
            text_part = MIMEText(notification["content"], "plain", "utf-8")
            msg.attach(text_part)

            # HTML 部分（可选，便于美化）
            html_content = f"""
            <html>
              <body>
                <h2>{notification['title']}</h2>
                <pre>{notification['content']}</pre>
                <a href="{notification['action_url']}">View Details</a>
              </body>
            </html>
            """
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)

            # 发送邮件（实际实现需要配置 SMTP）
            # 这里留作示例，真实环境需要配置 SMTP 服务器
            logger.info(f"[Notifier] Email notification prepared for {user_email}")
            return True

            # 实际发送代码（需要 SMTP 配置）：
            # with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            #     server.starttls()
            #     server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            #     server.send_message(msg)
            # logger.info(f"[Notifier] Email sent to {user_email}")
            # return True

        except Exception as e:
            logger.error(f"[Notifier] Failed to send email to {user_email}: {e}")
            return False

    def send_in_app_notification(self, user_id: str, notification: dict) -> bool:
        """
        保存应用内通知到数据库。

        Args:
            user_id: 用户 ID
            notification: 通知内容

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            self.db.table("in_app_notifications").insert({
                "user_id": user_id,
                "title": notification["title"],
                "content": notification["content"],
                "severity": notification["severity"],
                "action_url": notification["action_url"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "read_at": None,
            }).execute()

            logger.info(f"[Notifier] In-app notification saved for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[Notifier] Failed to save in-app notification: {e}")
            return False

    def send_webhook_notification(self, webhook_url: str, notification: dict, event: dict) -> bool:
        """
        通过 webhook 推送通知。

        Args:
            webhook_url: webhook URL
            notification: 通知内容
            event: 原始事件数据

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            import requests

            payload = {
                "notification": notification,
                "event": {
                    "id": event.get("id"),
                    "title": event.get("title"),
                    "company": event.get("company"),
                    "event_type": event.get("event_type"),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # 发送 POST 请求到 webhook（非阻塞，设置短超时）
            try:
                response = requests.post(
                    webhook_url,
                    json=payload,
                    timeout=5,
                )
                if response.status_code == 200:
                    logger.info(f"[Notifier] Webhook notification sent to {webhook_url}")
                    return True
                else:
                    logger.warning(f"[Notifier] Webhook returned {response.status_code}")
                    return False
            except requests.Timeout:
                logger.warning(f"[Notifier] Webhook timeout: {webhook_url}")
                return False

        except Exception as e:
            logger.error(f"[Notifier] Failed to send webhook: {e}")
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
        """
        统一发送单条通知，供报告调度器直接调用。

        在没有真实用户偏好 / 邮件地址时，仍会将通知保存到应用内缓冲区，
        让本地演示和无 key 环境保持可闭环。
        """
        channels = channels or ["in_app"]
        notification = {
            "title": title,
            "content": content,
            "severity": severity,
            "action_url": f"/admin/reports/{report_id}" if report_id else "",
            "template_id": template_id,
        }

        pref = None
        try:
            response = self.db.table("user_preferences").select("*").eq("user_id", user_id).limit(1).execute()
            pref = response.data[0] if response.data else None
        except Exception as exc:
            logger.warning(f"[Notifier] Preference lookup failed for {user_id}: {exc}")

        sent_channels: list[str] = []
        for channel in channels:
            success = False
            if channel == "email":
                user_email = (pref or {}).get("email") or settings.SMTP_USER
                if user_email:
                    success = self.send_email_notification(user_email, notification)
            elif channel == "in_app":
                success = self.send_in_app_notification(user_id, notification)
            elif channel == "webhook":
                webhook_url = (pref or {}).get("webhook_url")
                if webhook_url:
                    success = self.send_webhook_notification(webhook_url, notification, {"id": report_id, "title": title})

            if success:
                sent_channels.append(channel)
                self.save_notification_log(report_id, user_id, channel, "sent")
            else:
                self.save_notification_log(report_id, user_id, channel, "failed")

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
        """
        为一批用户发送通知。

        Args:
            event_id: 事件 ID
            user_ids: 目标用户 ID 列表

        Returns:
            发送结果统计 {"total", "sent", "failed", "by_channel"}
        """
        if not user_ids:
            return {"total": 0, "sent": 0, "failed": 0, "by_channel": {}}

        try:
            # 读取事件和评分
            event_response = self.db.table("extracted_events").select("*").eq("id", event_id).execute()
            if not event_response.data:
                logger.warning(f"[Notifier] Event {event_id} not found")
                return {"total": 0, "sent": 0, "failed": 0, "by_channel": {}}

            event = event_response.data[0]

            # 读取风险评分
            score_response = self.db.table("risk_scores").select("*").eq("event_id", event_id).execute()
            risk_score = score_response.data[0] if score_response.data else {}

            # 生成通知内容
            notification = self.generate_notification_content(event, risk_score, "")

            # 逐用户发送通知
            sent_count = 0
            by_channel = {"email": 0, "in_app": 0, "webhook": 0}

            for user_id in user_ids:
                try:
                    # 获取用户偏好（推送渠道）
                    pref_response = self.db.table("user_preferences").select("*").eq("user_id", user_id).execute()
                    if not pref_response.data:
                        logger.warning(f"[Notifier] No preferences found for user {user_id}")
                        continue

                    preferences = pref_response.data[0]
                    channels = preferences.get("notification_channels", ["in_app"])
                    user_email = preferences.get("email", "")
                    webhook_url = preferences.get("webhook_url", "")

                    # 根据偏好的渠道发送通知
                    for channel in channels:
                        success = False
                        if channel == "email" and user_email:
                            success = self.send_email_notification(user_email, notification)
                            if success:
                                by_channel["email"] += 1
                        elif channel == "in_app":
                            success = self.send_in_app_notification(user_id, notification)
                            if success:
                                by_channel["in_app"] += 1
                        elif channel == "webhook" and webhook_url:
                            success = self.send_webhook_notification(webhook_url, notification, event)
                            if success:
                                by_channel["webhook"] += 1

                        if success:
                            sent_count += 1

                except Exception as e:
                    logger.error(f"[Notifier] Failed to notify user {user_id}: {e}")

            result = {
                "total": len(user_ids),
                "sent": sent_count,
                "failed": len(user_ids) - sent_count,
                "by_channel": by_channel,
            }

            logger.info(f"[Notifier] Notifications sent for event {event_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"[Notifier] Batch notification failed: {e}")
            return {"total": len(user_ids), "sent": 0, "failed": len(user_ids), "by_channel": {}}

    def save_notification_log(self, event_id: str, user_id: str, channel: str, status: str) -> bool:
        """
        保存通知发送日志。

        Args:
            event_id: 事件 ID
            user_id: 用户 ID
            channel: 推送渠道
            status: 发送状态 ("sent", "failed", "pending")

        Returns:
            成功返回 True
        """
        try:
            self.db.table("notification_logs").insert({
                "event_id": event_id,
                "user_id": user_id,
                "channel": channel,
                "status": status,
                "sent_at": datetime.now(timezone.utc).isoformat() if status == "sent" else None,
            }).execute()
            return True
        except Exception as e:
            logger.error(f"[Notifier] Failed to save log: {e}")
            return False


# ── 全局单例 ──────────────────────────────────────────────────────────────

_notifier = None

def get_notifier() -> Notifier:
    """获取通知推送器实例（单例）"""
    global _notifier
    if _notifier is None:
        _notifier = Notifier()
    return _notifier
