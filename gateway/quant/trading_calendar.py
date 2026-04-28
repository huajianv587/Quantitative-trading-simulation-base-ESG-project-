from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from gateway.config import settings


NY_TZ = ZoneInfo("America/New_York")


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(NY_TZ).date() if value.tzinfo else value.date()
    text = str(value or "").strip()
    if len(text) >= 10:
        return date.fromisoformat(text[:10])
    return datetime.now(NY_TZ).date()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@dataclass(frozen=True)
class SessionInfo:
    calendar_id: str
    session_date: str
    is_session: bool
    open_at: datetime | None
    close_at: datetime | None
    early_close: bool
    previous_session: str | None
    next_session: str | None

    def model_dump(self) -> dict[str, Any]:
        return {
            "calendar_id": self.calendar_id,
            "session_date": self.session_date,
            "is_session": self.is_session,
            "open_at": _iso(self.open_at),
            "close_at": _iso(self.close_at),
            "early_close": self.early_close,
            "previous_session": self.previous_session,
            "next_session": self.next_session,
        }


class TradingCalendarService:
    """Small XNYS calendar facade with pandas-market-calendars fallback."""

    def __init__(self, calendar_id: str | None = None) -> None:
        self.calendar_id = str(calendar_id or getattr(settings, "TRADING_CALENDAR_ID", "XNYS") or "XNYS").upper()
        self.timezone = NY_TZ
        self._calendar = None
        try:
            import pandas_market_calendars as mcal

            self._calendar = mcal.get_calendar("NYSE" if self.calendar_id in {"XNYS", "NYSE"} else self.calendar_id)
        except Exception:
            self._calendar = None

    def now(self) -> datetime:
        return datetime.now(self.timezone)

    def session_info(self, day: date | str | datetime | None = None) -> SessionInfo:
        target = _parse_date(day or self.now())
        bounds = self.session_bounds(target)
        return SessionInfo(
            calendar_id=self.calendar_id,
            session_date=target.isoformat(),
            is_session=bounds is not None,
            open_at=bounds[0] if bounds else None,
            close_at=bounds[1] if bounds else None,
            early_close=bool(bounds and bounds[2]),
            previous_session=self.previous_session(target),
            next_session=self.next_session(target),
        )

    def status(self, at: datetime | None = None, market_clock: dict[str, Any] | None = None) -> dict[str, Any]:
        current = at.astimezone(self.timezone) if at and at.tzinfo else (at.replace(tzinfo=self.timezone) if at else self.now())
        info = self.session_info(current)
        open_at = info.open_at
        close_at = info.close_at
        is_open_by_calendar = bool(info.is_session and open_at and close_at and open_at <= current <= close_at)
        clock = dict(market_clock or {})
        clock_available = bool(clock)
        clock_is_open = clock.get("is_open")
        if clock_is_open is None:
            effective_open = is_open_by_calendar
            clock_status = "unavailable"
        else:
            effective_open = bool(clock_is_open)
            clock_status = "open" if effective_open else "closed"
        return {
            **info.model_dump(),
            "timezone": str(self.timezone),
            "now": current.isoformat(),
            "is_open_by_calendar": is_open_by_calendar,
            "market_clock_available": clock_available,
            "market_clock_status": clock_status,
            "market_clock": clock,
            "effective_market_open": effective_open,
            "require_trading_session": bool(getattr(settings, "SCHEDULER_REQUIRE_TRADING_SESSION", True)),
            "require_market_clock_for_submit": bool(getattr(settings, "SCHEDULER_REQUIRE_MARKET_CLOCK_FOR_SUBMIT", True)),
        }

    def is_session(self, day: date | str | datetime) -> bool:
        return self.session_bounds(_parse_date(day)) is not None

    def session_bounds(self, day: date | str | datetime) -> tuple[datetime, datetime, bool] | None:
        target = _parse_date(day)
        if self._calendar is not None:
            try:
                schedule = self._calendar.schedule(start_date=target.isoformat(), end_date=target.isoformat())
                if schedule.empty:
                    return None
                row = schedule.iloc[0]
                open_at = row["market_open"].to_pydatetime().astimezone(self.timezone)
                close_at = row["market_close"].to_pydatetime().astimezone(self.timezone)
                early_close = close_at.time() < time(16, 0)
                return open_at, close_at, early_close
            except Exception:
                pass
        if not self._fallback_is_session(target):
            return None
        close_hour = 13 if self._fallback_is_early_close(target) else 16
        open_at = datetime.combine(target, time(9, 30), tzinfo=self.timezone)
        close_at = datetime.combine(target, time(close_hour, 0), tzinfo=self.timezone)
        return open_at, close_at, close_hour < 16

    def previous_session(self, day: date | str | datetime | None = None) -> str | None:
        current = _parse_date(day or self.now()) - timedelta(days=1)
        for _ in range(370):
            if self.is_session(current):
                return current.isoformat()
            current -= timedelta(days=1)
        return None

    def next_session(self, day: date | str | datetime | None = None) -> str | None:
        current = _parse_date(day or self.now()) + timedelta(days=1)
        for _ in range(370):
            if self.is_session(current):
                return current.isoformat()
            current += timedelta(days=1)
        return None

    def session_after(self, start: date | str | datetime, sessions: int) -> str:
        current = _parse_date(start)
        remaining = max(0, int(sessions))
        while remaining:
            current += timedelta(days=1)
            if self.is_session(current):
                remaining -= 1
        return current.isoformat()

    def sync_end_hhmm(self, day: date | str | datetime | None = None) -> str:
        info = self.session_info(day or self.now())
        close_at = info.close_at or datetime.combine(_parse_date(day or self.now()), time(16, 0), tzinfo=self.timezone)
        close_at = close_at + timedelta(minutes=max(0, int(getattr(settings, "SCHEDULER_CLOSE_GRACE_MINUTES", 10) or 10)))
        return close_at.strftime("%H:%M")

    @staticmethod
    def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
        raw = date(year, month, day)
        if raw.weekday() == 5:
            return raw - timedelta(days=1)
        if raw.weekday() == 6:
            return raw + timedelta(days=1)
        return raw

    @staticmethod
    def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
        current = date(year, month, 1)
        while current.weekday() != weekday:
            current += timedelta(days=1)
        return current + timedelta(days=7 * (nth - 1))

    @staticmethod
    def _last_weekday(year: int, month: int, weekday: int) -> date:
        current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        while current.weekday() != weekday:
            current -= timedelta(days=1)
        return current

    @classmethod
    def _good_friday(cls, year: int) -> date:
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day) - timedelta(days=2)

    @classmethod
    def _fallback_holidays(cls, year: int) -> set[date]:
        thanksgiving = cls._nth_weekday(year, 11, 3, 4)
        return {
            cls._observed_fixed_holiday(year, 1, 1),
            cls._nth_weekday(year, 1, 0, 3),
            cls._nth_weekday(year, 2, 0, 3),
            cls._good_friday(year),
            cls._last_weekday(year, 5, 0),
            cls._observed_fixed_holiday(year, 6, 19),
            cls._observed_fixed_holiday(year, 7, 4),
            cls._nth_weekday(year, 9, 0, 1),
            thanksgiving,
            cls._observed_fixed_holiday(year, 12, 25),
        }

    @classmethod
    def _fallback_is_session(cls, day: date) -> bool:
        return day.weekday() < 5 and day not in cls._fallback_holidays(day.year)

    @classmethod
    def _fallback_is_early_close(cls, day: date) -> bool:
        thanksgiving = cls._nth_weekday(day.year, 11, 3, 4)
        christmas_eve = date(day.year, 12, 24)
        independence_eve = date(day.year, 7, 3)
        return day in {thanksgiving + timedelta(days=1), christmas_eve, independence_eve} and day.weekday() < 5

