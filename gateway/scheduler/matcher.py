# matcher.py — 事件-用户匹配模块
# 职责：根据用户的偏好和关注，筛选相关的 ESG 事件
# 这是个性化推送的关键：把所有事件 → 每个用户的相关事件

from datetime import datetime, timezone
from typing import Optional

from gateway.utils.logger import get_logger
from gateway.models.schemas import UserPreference, RiskLevel
from gateway.db.supabase_client import get_client

logger = get_logger(__name__)


class EventMatcher:
    """事件-用户偏好匹配器"""

    def __init__(self):
        self.db = get_client()

    def get_user_preferences(self, user_id: str) -> Optional[dict]:
        """
        从数据库获取用户偏好。

        Args:
            user_id: 用户 ID

        Returns:
            用户偏好对象，未找到返回 None
        """
        try:
            response = self.db.table("user_preferences").select("*").eq("user_id", user_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"[Matcher] Failed to fetch preferences for user {user_id}: {e}")
            return None

    def is_event_relevant(self, event: dict, preferences: dict) -> bool:
        """
        判断事件是否与用户偏好匹配。

        匹配规则：
        1. 公司过滤：事件公司必须在用户的关注公司清单中（或为空表示关注所有）
        2. 类别过滤：事件的 impact_area (E/S/G) 必须在用户的关注类别中
        3. 严重性过滤：事件的风险等级 >= 用户的风险阈值
        4. 关键词过滤：事件标题/描述中包含任意用户关键词

        Args:
            event: 提取后的事件对象 {"company", "impact_area", "severity", "title", "description", ...}
            preferences: 用户偏好 {"interested_companies", "interested_categories", "risk_threshold", "keywords", ...}

        Returns:
            True 如果匹配，False 否则
        """
        # 公司过滤
        interested_companies = preferences.get("interested_companies", [])
        if interested_companies and event.get("company") not in interested_companies:
            return False

        # 类别过滤
        interested_categories = preferences.get("interested_categories", ["E", "S", "G"])
        if event.get("impact_area") not in interested_categories:
            return False

        # 严重性过滤
        risk_threshold = preferences.get("risk_threshold", "low")
        event_severity = event.get("severity", "low")
        if not self._is_severity_high_enough(event_severity, risk_threshold):
            return False

        # 关键词过滤（可选）
        keywords = preferences.get("keywords", [])
        if keywords:
            title = event.get("title", "").lower()
            description = event.get("description", "").lower()
            if not any(kw.lower() in title or kw.lower() in description for kw in keywords):
                return False

        return True

    def _is_severity_high_enough(self, event_severity: str, threshold: str) -> bool:
        """
        判断事件严重性是否达到用户的阈值。

        严重性排序：low < medium < high < critical

        Args:
            event_severity: 事件的严重性等级
            threshold: 用户的风险阈值

        Returns:
            True 如果事件严重性 >= 阈值
        """
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return severity_order.get(event_severity, 0) >= severity_order.get(threshold, 0)

    def find_matching_users(self, event: dict) -> list[str]:
        """
        找出所有与该事件相关的用户。

        Args:
            event: 提取后的事件对象

        Returns:
            匹配的用户 ID 列表
        """
        matching_users = []

        try:
            # 获取所有用户偏好
            response = self.db.table("user_preferences").select("*").execute()
            all_preferences = response.data

            for pref in all_preferences:
                user_id = pref.get("user_id")
                if self.is_event_relevant(event, pref):
                    matching_users.append(user_id)
                    logger.debug(f"[Matcher] Event matched user {user_id}")

            logger.info(f"[Matcher] Event matched {len(matching_users)} users")

        except Exception as e:
            logger.error(f"[Matcher] Failed to find matching users: {e}")

        return matching_users

    def match_event_to_users(self, event_id: str) -> dict:
        """
        为一个事件找出所有匹配的用户，保存匹配记录。

        Args:
            event_id: 事件 ID

        Returns:
            匹配结果 {"event_id", "matched_users", "match_count"}
        """
        try:
            # 从数据库读取事件
            response = self.db.table("extracted_events").select("*").eq("id", event_id).execute()
            if not response.data:
                logger.warning(f"[Matcher] Event {event_id} not found")
                return {"event_id": event_id, "matched_users": [], "match_count": 0}

            event = response.data[0]

            # 找匹配的用户
            matched_users = self.find_matching_users(event)

            # 保存匹配记录到 event_user_matches 表
            if matched_users:
                matches_to_insert = [
                    {
                        "event_id": event_id,
                        "user_id": user_id,
                        "matched_at": datetime.now(timezone.utc).isoformat(),
                    }
                    for user_id in matched_users
                ]
                self.db.table("event_user_matches").insert(matches_to_insert).execute()
                logger.info(f"[Matcher] Saved {len(matched_users)} matches for event {event_id}")

            result = {
                "event_id": event_id,
                "matched_users": matched_users,
                "match_count": len(matched_users),
            }

            return result

        except Exception as e:
            logger.error(f"[Matcher] Matching failed for event {event_id}: {e}")
            return {"event_id": event_id, "matched_users": [], "match_count": 0, "error": str(e)}

    def match_batch_events(self, event_ids: list[str]) -> dict:
        """
        批量匹配多个事件。

        Args:
            event_ids: 事件 ID 列表

        Returns:
            批量匹配结果统计
        """
        if not event_ids:
            return {"total_events": 0, "total_matches": 0, "results": []}

        results = []
        total_matches = 0

        for event_id in event_ids:
            result = self.match_event_to_users(event_id)
            results.append(result)
            total_matches += result.get("match_count", 0)

        summary = {
            "total_events": len(event_ids),
            "total_matches": total_matches,
            "avg_matches_per_event": total_matches / len(event_ids) if event_ids else 0,
            "results": results,
        }

        logger.info(f"[Matcher] Batch matching complete: {summary}")
        return summary

    def create_or_update_preference(self, user_id: str, preferences: dict) -> bool:
        """
        创建或更新用户偏好。

        Args:
            user_id: 用户 ID
            preferences: 偏好数据 {
                "interested_companies": ["Tesla", "Microsoft"],
                "interested_categories": ["E", "S"],
                "risk_threshold": "medium",
                "keywords": ["carbon", "renewable"],
                "notification_channels": ["email", "in_app"]
            }

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            # 检查是否已存在
            response = self.db.table("user_preferences").select("id").eq("user_id", user_id).execute()

            data = {
                "user_id": user_id,
                **preferences,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if response.data:
                # 更新
                self.db.table("user_preferences").update(data).eq("user_id", user_id).execute()
                logger.info(f"[Matcher] Updated preferences for user {user_id}")
            else:
                # 创建
                data["created_at"] = datetime.now(timezone.utc).isoformat()
                self.db.table("user_preferences").insert(data).execute()
                logger.info(f"[Matcher] Created preferences for user {user_id}")

            return True

        except Exception as e:
            logger.error(f"[Matcher] Failed to save preferences for user {user_id}: {e}")
            return False


# ── 全局单例 ──────────────────────────────────────────────────────────────

_matcher = None

def get_matcher() -> EventMatcher:
    """获取匹配器实例（单例）"""
    global _matcher
    if _matcher is None:
        _matcher = EventMatcher()
    return _matcher
