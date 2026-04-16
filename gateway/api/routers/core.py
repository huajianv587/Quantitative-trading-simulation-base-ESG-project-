from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from gateway.app_runtime import runtime
from gateway.config import settings
from gateway.utils.llm_client import get_runtime_backend_status
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _product_site_entry() -> Path | None:
    project_root = Path(__file__).resolve().parents[3]
    candidates = [
        project_root / "esg_quant_landing_v2.html",
        project_root / "dist" / "index.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _module_status(request: Request) -> dict[str, bool]:
    query_engine = getattr(request.app.state, "query_engine", None)
    return {
        "rag": query_engine is not None,
        "esg_scorer": runtime.esg_scorer is not None,
        "report_scheduler": runtime.report_scheduler is not None,
        "quant_system": runtime.quant_system is not None,
    }


def _load_recent_signals(generated_at: datetime) -> tuple[list[dict[str, Any]], str]:
    recent_signals: list[dict[str, Any]] = []
    signal_source = "database"

    if runtime.get_client is not None:
        try:
            db = runtime.get_client()
            response = (
                db.table("esg_events")
                .select("id,title,company,event_type,source,source_url,detected_at,created_at,raw_content")
                .order("detected_at", desc=True)
                .limit(6)
                .execute()
            )

            for item in response.data or []:
                description = (
                    item.get("description")
                    or item.get("raw_content")
                    or "最新 ESG 动态已进入监控队列。"
                )
                recent_signals.append({
                    "id": item.get("id"),
                    "company": item.get("company") or "市场观察",
                    "title": item.get("title") or "新的 ESG 事件",
                    "description": description,
                    "event_type": item.get("event_type") or "update",
                    "source": item.get("source") or "database",
                    "source_url": item.get("source_url"),
                    "detected_at": item.get("detected_at") or item.get("created_at"),
                    "tone": "alert" if "rule" in str(item.get("title", "")).lower() else "positive",
                })
        except Exception as exc:
            signal_source = "scanner_fallback"
            logger.warning(f"[Dashboard] Failed to load recent signals from database: {exc}")
    else:
        signal_source = "scanner_fallback"

    if recent_signals:
        return recent_signals, signal_source

    signal_source = "scanner_fallback"
    try:
        from gateway.scheduler.scanner import get_scanner

        scanner = get_scanner()
        sample_events = []
        sample_events.extend(scanner.scan_news_feeds()[0])
        sample_events.extend(scanner.scan_esg_reports()[0])
        sample_events.extend(scanner.scan_compliance_updates()[0])

        tone_map = {
            "EMISSION_REDUCTION": "positive",
            "RENEWABLE_ENERGY": "positive",
            "GOVERNANCE_CHANGE": "alert",
        }

        for idx, event in enumerate(sample_events[:6]):
            event_type = str(event.event_type).split(".")[-1] if event.event_type else "UPDATE"
            recent_signals.append({
                "id": f"sample-{idx}",
                "company": event.company or "市场观察",
                "title": event.title,
                "description": event.description,
                "event_type": event_type,
                "source": event.source,
                "source_url": event.source_url,
                "detected_at": event.detected_at.isoformat(),
                "tone": tone_map.get(event_type, "neutral"),
            })
    except Exception as exc:
        logger.warning(f"[Dashboard] Scanner fallback unavailable: {exc}")

    if recent_signals:
        return recent_signals, signal_source

    return [
        {
            "id": "fallback-1",
            "company": "Tesla",
            "title": "Tesla 更新碳减排目标",
            "description": "环境目标被重新量化，市场关注其供应链执行速度。",
            "event_type": "EMISSION_REDUCTION",
            "source": "fallback",
            "source_url": None,
            "detected_at": generated_at.isoformat(),
            "tone": "positive",
        },
        {
            "id": "fallback-2",
            "company": "Microsoft",
            "title": "Microsoft 发布最新 ESG 报告",
            "description": "报告强调可再生能源与治理透明度提升。",
            "event_type": "RENEWABLE_ENERGY",
            "source": "fallback",
            "source_url": None,
            "detected_at": generated_at.isoformat(),
            "tone": "positive",
        },
        {
            "id": "fallback-3",
            "company": "SEC",
            "title": "新的 ESG 披露规则进入市场视野",
            "description": "治理与合规要求进一步趋严，企业披露压力抬升。",
            "event_type": "GOVERNANCE_CHANGE",
            "source": "fallback",
            "source_url": None,
            "detected_at": generated_at.isoformat(),
            "tone": "alert",
        },
    ], "static_fallback"


def _build_score_snapshot(spotlight_company: str) -> dict[str, Any]:
    score_profiles = {
        "tesla": {
            "overall_score": 72,
            "confidence": 0.85,
            "dimensions": {"E": 78, "S": 65, "G": 73},
        },
        "microsoft": {
            "overall_score": 81,
            "confidence": 0.89,
            "dimensions": {"E": 84, "S": 77, "G": 82},
        },
        "apple": {
            "overall_score": 79,
            "confidence": 0.87,
            "dimensions": {"E": 82, "S": 74, "G": 79},
        },
    }
    score_profile = score_profiles.get(str(spotlight_company).lower(), {
        "overall_score": 74,
        "confidence": 0.83,
        "dimensions": {"E": 77, "S": 69, "G": 75},
    })

    return {
        "company": spotlight_company,
        "overall_score": score_profile["overall_score"],
        "confidence": score_profile["confidence"],
        "dimensions": [
            {"key": "E", "label": "环保", "score": score_profile["dimensions"]["E"], "trend": "up"},
            {"key": "S", "label": "社会", "score": score_profile["dimensions"]["S"], "trend": "stable"},
            {"key": "G", "label": "治理", "score": score_profile["dimensions"]["G"], "trend": "up"},
        ],
        "radar": [
            {"label": "碳排放", "value": min(95, score_profile["dimensions"]["E"] + 6)},
            {"label": "员工满意度", "value": min(95, score_profile["dimensions"]["S"] + 4)},
            {"label": "供应链伦理", "value": max(52, score_profile["dimensions"]["S"] - 3)},
            {"label": "能源效率", "value": min(95, score_profile["dimensions"]["E"] + 2)},
            {"label": "成本竞争力", "value": min(95, score_profile["dimensions"]["G"] + 1)},
        ],
        "trend": [
            {"month": "Jan", "E": 64, "S": 58, "G": 60},
            {"month": "Feb", "E": 67, "S": 60, "G": 63},
            {"month": "Mar", "E": 70, "S": 61, "G": 66},
            {"month": "Apr", "E": 69, "S": 62, "G": 67},
            {"month": "May", "E": 72, "S": 63, "G": 68},
            {"month": "Jun", "E": 73, "S": 63, "G": 69},
            {"month": "Jul", "E": 74, "S": 64, "G": 70},
            {"month": "Aug", "E": 76, "S": 64, "G": 71},
            {
                "month": "Sep",
                "E": score_profile["dimensions"]["E"] - 1,
                "S": score_profile["dimensions"]["S"],
                "G": score_profile["dimensions"]["G"] - 1,
            },
            {
                "month": "Oct",
                "E": score_profile["dimensions"]["E"],
                "S": score_profile["dimensions"]["S"],
                "G": score_profile["dimensions"]["G"],
            },
        ],
    }


def _build_event_monitor(recent_signals: list[dict[str, Any]], generated_at: datetime) -> dict[str, Any]:
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    monitor_events = []
    timeline = []

    for index, item in enumerate(recent_signals[:5]):
        tone = item.get("tone") or "neutral"
        if tone == "alert" and risk_counts["high"] == 0:
            level = "high"
            risk_score = 89 - index * 3
        elif tone == "alert":
            level = "medium"
            risk_score = 67 - index * 2
        elif tone == "positive":
            level = "low"
            risk_score = 46 + index * 2
        else:
            level = "medium"
            risk_score = 58 - index

        risk_counts[level] += 1

        recommendation = (
            "持续跟踪披露进度并评估治理回应质量。"
            if level == "high" else
            "补充行业对标并观察后续执行动作。"
            if level == "medium" else
            "作为正面样本持续观察，提炼可复用亮点。"
        )

        monitor_events.append({
            "company": item.get("company") or "市场观察",
            "title": item.get("title") or "新的 ESG 事件",
            "description": item.get("description") or "最新 ESG 动态已进入视野。",
            "level": level,
            "risk_score": max(28, min(96, risk_score)),
            "published_at": item.get("detected_at") or generated_at.isoformat(),
            "event_type": item.get("event_type") or "UPDATE",
            "recommendation": recommendation,
            "positive": tone == "positive",
        })

        timeline.append({
            "date_label": datetime.fromisoformat(
                str(item.get("detected_at") or generated_at.isoformat()).replace("Z", "+00:00")
            ).strftime("%m/%d"),
            "company": item.get("company") or "市场观察",
            "level": level,
        })

    return {
        "period_label": "最近 7 天",
        "risk_counts": risk_counts,
        "events": monitor_events,
        "timeline": timeline,
    }


@router.get("/health")
def health(request: Request):
    modules = _module_status(request)

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "app_mode": settings.APP_MODE,
        "runtime": get_runtime_backend_status(),
        "ready": all(modules.values()),
        "modules": modules,
    }


@router.get("/health/ready")
def health_ready(request: Request):
    payload = health(request)
    if payload["ready"]:
        return payload
    return JSONResponse(status_code=503, content=payload)


@router.get("/", include_in_schema=False)
def root():
    product_site = _product_site_entry()
    if product_site is not None:
        return FileResponse(product_site)
    return RedirectResponse(url="/app/#/dashboard", status_code=307)


@router.get("/dashboard/overview")
def dashboard_overview(request: Request):
    if runtime.quant_system is not None:
        try:
            return runtime.quant_system.build_dashboard_overview()
        except Exception as exc:
            logger.warning(f"[Dashboard] Quant overview unavailable, falling back: {exc}")

    generated_at = datetime.now(timezone.utc)
    health_modules = {
        **_module_status(request),
        "data_sources": runtime.data_source_manager is not None,
    }

    recent_signals, signal_source = _load_recent_signals(generated_at)

    try:
        scheduler_summary = runtime.get_scheduler_statistics(7)
    except Exception as exc:
        logger.warning(f"[Dashboard] Scheduler summary unavailable: {exc}")
        scheduler_summary = {
            "total_scans": 0,
            "success_rate": 0,
            "last_sync_time": None,
            "degraded": True,
            "message": "Scheduler summary unavailable",
        }

    total_signals = len(recent_signals)
    tracked_companies = len({item["company"] for item in recent_signals if item.get("company")})
    active_modules = sum(1 for ready in health_modules.values() if ready)

    spotlight = recent_signals[0]
    spotlight_company = spotlight.get("company") or "Tesla"
    score_snapshot = _build_score_snapshot(spotlight_company)
    event_monitor = _build_event_monitor(recent_signals, generated_at)

    return {
        "generated_at": generated_at.isoformat(),
        "source": signal_source,
        "health": health_modules,
        "spotlight": spotlight,
        "metrics": [
            {
                "label": "实时信号",
                "value": total_signals,
                "suffix": "条",
                "hint": "最近进入旗舰首页的信息流",
            },
            {
                "label": "覆盖主体",
                "value": tracked_companies,
                "suffix": "个",
                "hint": "当前热点涉及的企业或监管主体",
            },
            {
                "label": "系统模块",
                "value": active_modules,
                "suffix": f"/{len(health_modules)}",
                "hint": "当前在线的分析与调度能力",
            },
            {
                "label": "近 7 天扫描",
                "value": scheduler_summary.get("total_scans", 0),
                "suffix": "次",
                "hint": "调度器扫描统计",
            },
        ],
        "signals": recent_signals,
        "query_interface": {
            "hot_questions": [
                f"{spotlight_company} 的 ESG 综合评分是多少？",
                f"{spotlight_company} 最近有哪些 ESG 风险事件？",
                "苹果与微软的社会责任表现如何对比？",
                "最近 7 天有哪些值得关注的 ESG 风险信号？",
            ],
        },
        "score_snapshot": score_snapshot,
        "event_monitor": event_monitor,
        "narrative": {
            "headline": "ESG 智能中枢",
            "subheadline": "像旗舰发布页一样呈现 ESG 情报、评分看板、事件监测与执行入口。",
            "summary": "将 QueryInterface、ScoreBoard、EventMonitor 和功能矩阵收束成一个高端总览页面，让信息一眼可读、功能一键可达。",
        },
    }


@router.get("/market/ohlcv")
def market_ohlcv(symbol: str = "NVDA", timeframe: str = "1D", limit: int = 120):
    """
    Fetch OHLCV candlestick data for a symbol.
    Uses yfinance as primary source (free, no API key needed).
    Falls back to synthetic data if yfinance unavailable.
    """
    tf_map = {"1D": "1d", "1W": "1wk", "1M": "1mo", "3M": "1d", "1Y": "1d"}
    periods = {"1D": "6mo", "1W": "1y", "1M": "2y", "3M": "1y", "1Y": "5y"}
    yf_interval = tf_map.get(timeframe, "1d")
    yf_period   = periods.get(timeframe, "6mo")

    try:
        import yfinance as yf  # type: ignore
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period=yf_period, interval=yf_interval)
        if hist.empty:
            raise ValueError("No data returned")
        candles = []
        for ts, row in hist.tail(limit).iterrows():
            candles.append({
                "t": ts.strftime("%Y-%m-%d"),
                "o": round(float(row["Open"]), 4),
                "h": round(float(row["High"]), 4),
                "l": round(float(row["Low"]), 4),
                "c": round(float(row["Close"]), 4),
                "v": int(row["Volume"]),
            })
        return {"symbol": symbol.upper(), "timeframe": timeframe, "source": "yfinance", "candles": candles}
    except Exception as exc:
        logger.warning(f"[OHLCV] yfinance failed for {symbol}: {exc}. Using synthetic data.")
        # Synthetic fallback — realistic price walk
        import math, random
        random.seed(hash(symbol) % 10000)
        base_prices = {"NVDA": 480, "TSLA": 175, "AAPL": 185, "MSFT": 415, "GOOGL": 155,
                       "AMZN": 195, "META": 520, "AMGN": 270, "NEE": 72, "SPY": 510}
        price = float(base_prices.get(symbol.upper(), 200))
        from datetime import date, timedelta
        start = date.today() - timedelta(days=limit * (7 if timeframe == "1W" else 1))
        candles = []
        for i in range(min(limit, 180)):
            vol = 0.012 + random.random() * 0.008
            o = price
            c = price * (1 + (random.random() - 0.48) * vol * 2)
            h = max(o, c) * (1 + random.random() * vol * 0.5)
            l = min(o, c) * (1 - random.random() * vol * 0.5)
            v = int((800 + random.random() * 3000) * 1000)
            candles.append({
                "t": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
                "o": round(o, 2), "h": round(h, 2), "l": round(l, 2),
                "c": round(c, 2), "v": v,
            })
            price = c
        return {"symbol": symbol.upper(), "timeframe": timeframe, "source": "synthetic", "candles": candles}
