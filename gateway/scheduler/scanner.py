from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from gateway.db.supabase_client import get_client
from gateway.models.schemas import ESGEvent, ESGEventType
from gateway.scheduler.data_sources import DataSourceManager
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class Scanner:
    """Real-source ESG scanner for news, filings, and SEC-only compliance updates."""

    NEWS_LANE = "news"
    REPORTS_LANE = "reports"
    COMPLIANCE_LANE = "compliance"

    REPORT_FORMS = ("10-K", "10-K/A", "DEF 14A", "8-K")
    COMPLIANCE_FORMS = ("DEF 14A", "8-K", "10-K", "10-K/A")
    COMPLIANCE_KEYWORDS = (
        "material weakness",
        "internal control",
        "non-compliance",
        "compliance",
        "investigation",
        "subpoena",
        "restatement",
        "shareholder rights",
        "board of directors",
        "independent chair",
        "lead independent director",
        "audit committee",
        "whistleblower",
        "anti-corruption",
        "anti bribery",
        "anti-bribery",
        "bribery",
        "corruption",
        "fcpa",
        "climate-related",
        "disclosure controls",
    )

    def __init__(self):
        self.db = get_client()
        self.data_source_manager = DataSourceManager()
        self._last_run_summary: dict[str, Any] = {}
        self._last_lane_results: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_company_key(value: str) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)

        raw = str(value).strip()
        if not raw:
            return None
        if raw.isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)

        raw = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @classmethod
    def _isoformat(cls, value: Any) -> Optional[str]:
        parsed = cls._coerce_datetime(value)
        if parsed is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _json_loads(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _event_type_value(event_type: ESGEventType | str) -> str:
        if isinstance(event_type, ESGEventType):
            return event_type.value
        return str(event_type)

    @staticmethod
    def _dedupe_strings(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen = set()
        for item in values:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            deduped.append(normalized)
            seen.add(normalized)
        return deduped

    def _build_blocked_state(self, *, reason: str, next_actions: list[str]) -> dict[str, Any]:
        return {
            "status": "blocked",
            "block_reason": reason,
            "next_actions": self._dedupe_strings(next_actions),
        }

    def _fetch_rows(self, table: str, columns: str = "*", **filters: Any) -> list[dict[str, Any]]:
        try:
            query = self.db.table(table).select(columns)
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.execute()
            return [dict(row) for row in (response.data or [])]
        except Exception as exc:
            logger.warning(f"[Scanner] Failed to fetch rows from {table}: {exc}")
            return []

    def _get_interest_companies(self) -> list[str]:
        companies: list[str] = []
        for pref in self._fetch_rows("user_preferences", "interested_companies"):
            companies.extend(pref.get("interested_companies") or [])
        return self._dedupe_strings(companies)

    def _get_holding_companies(self) -> list[str]:
        companies: list[str] = []
        rows = self._fetch_rows("user_holdings", "company_name,company")
        for row in rows:
            if row.get("company_name"):
                companies.append(row["company_name"])
            elif row.get("company"):
                companies.append(row["company"])
        return self._dedupe_strings(companies)

    def _get_tracked_companies(self) -> list[str]:
        companies = []
        companies.extend(self._get_interest_companies())
        companies.extend(self._get_holding_companies())
        return self._dedupe_strings(sorted(companies))

    def _load_source_state(self, *, lane: str, source_key: str, company_key: str) -> dict[str, Any]:
        rows = self._fetch_rows(
            "scan_source_state",
            "id,lane,source_key,company_key,checkpoint_value,last_status,blocked_reason,events_found,events_saved,updated_at",
            lane=lane,
            source_key=source_key,
            company_key=company_key,
        )
        if not rows:
            return {}
        row = rows[0]
        row["checkpoint_value"] = self._json_loads(row.get("checkpoint_value"))
        return row

    def _save_source_state(
        self,
        *,
        lane: str,
        source_key: str,
        company_key: str,
        checkpoint_value: dict[str, Any],
        status: str,
        blocked_reason: Optional[str],
        events_found: int,
        events_saved: int,
    ) -> None:
        payload = {
            "lane": lane,
            "source_key": source_key,
            "company_key": company_key,
            "checkpoint_value": checkpoint_value,
            "last_status": status,
            "blocked_reason": blocked_reason,
            "events_found": events_found,
            "events_saved": events_saved,
            "updated_at": self._utcnow().isoformat(),
        }
        try:
            existing = self._fetch_rows(
                "scan_source_state",
                "id",
                lane=lane,
                source_key=source_key,
                company_key=company_key,
            )
            if existing:
                self.db.table("scan_source_state").update(payload).eq("id", existing[0]["id"]).execute()
            else:
                self.db.table("scan_source_state").insert(payload).execute()
        except Exception as exc:
            logger.warning(
                f"[Scanner] Failed to persist source state for {lane}/{source_key}/{company_key}: {exc}"
            )

    def _news_checkpoint_key(self, article: dict[str, Any]) -> tuple[str, str, str]:
        published_at = self._isoformat(article.get("published_at")) or ""
        url = str(article.get("url") or "").strip()
        title = str(article.get("title") or "").strip()
        return (published_at, url, title)

    def _filing_checkpoint_key(self, filing: dict[str, Any]) -> tuple[str, str, str]:
        filed_at = self._isoformat(filing.get("filed_at")) or ""
        accession = str(filing.get("accession_number") or "").strip()
        form = str(filing.get("form") or "").strip()
        return (filed_at, accession, form)

    def _is_new_news_item(self, article: dict[str, Any], checkpoint: dict[str, Any]) -> bool:
        if not checkpoint:
            return True
        return self._news_checkpoint_key(article) > (
            str(checkpoint.get("published_at") or ""),
            str(checkpoint.get("url") or ""),
            str(checkpoint.get("title") or ""),
        )

    def _is_new_filing(self, filing: dict[str, Any], checkpoint: dict[str, Any]) -> bool:
        if not checkpoint:
            return True
        return self._filing_checkpoint_key(filing) > (
            str(checkpoint.get("filed_at") or ""),
            str(checkpoint.get("accession_number") or ""),
            str(checkpoint.get("form") or ""),
        )

    def _classify_event_type(self, *, title: str, description: str, default: ESGEventType = ESGEventType.OTHER) -> ESGEventType:
        text = f"{title} {description}".lower()
        if any(keyword in text for keyword in ("bribery", "corruption", "fcpa", "kickback")):
            return ESGEventType.CORRUPTION_ALLEGATION
        if any(keyword in text for keyword in ("violation", "non-compliance", "restatement", "investigation", "subpoena", "material weakness")):
            return ESGEventType.COMPLIANCE_VIOLATION
        if any(keyword in text for keyword in ("board", "director", "proxy", "governance", "audit committee", "whistleblower")):
            return ESGEventType.GOVERNANCE_CHANGE
        if any(keyword in text for keyword in ("carbon", "emission", "climate", "net zero", "renewable", "sustainability")):
            return ESGEventType.EMISSION_REDUCTION
        if any(keyword in text for keyword in ("water", "waste", "recycling")):
            return ESGEventType.WATER_MANAGEMENT
        if any(keyword in text for keyword in ("safety", "injury", "accident", "fire", "recall")):
            return ESGEventType.SAFETY_INCIDENT
        if any(keyword in text for keyword in ("diversity", "equity", "inclusion", "women", "workforce")):
            return ESGEventType.DIVERSITY_INITIATIVE
        if any(keyword in text for keyword in ("community", "charity", "volunteer", "education")):
            return ESGEventType.COMMUNITY_ENGAGEMENT
        return default

    def _existing_event_key(self, event: ESGEvent) -> Optional[str]:
        try:
            query = self.db.table("esg_events").select("id")
            if event.source_url:
                query = query.eq("source_url", event.source_url)
            else:
                query = (
                    query.eq("company", event.company)
                    .eq("title", event.title)
                    .eq("source", event.source)
                )
            response = query.limit(1).execute()
            row = (response.data or [None])[0]
            if row:
                return str(row.get("id"))
        except Exception as exc:
            logger.warning(f"[Scanner] Existing-event lookup failed: {exc}")
        return None

    def _create_scan_job(self) -> Optional[str]:
        payload = {
            "job_type": "scheduled_scan",
            "status": "running",
            "started_at": self._utcnow().isoformat(),
            "events_found": 0,
            "events_saved": 0,
            "source_summary": {},
            "next_actions": [],
            "checkpoint_state": {},
            "created_at": self._utcnow().isoformat(),
        }
        try:
            response = self.db.table("scan_jobs").insert(payload).execute()
            rows = response.data or []
            if rows:
                return str(rows[0].get("id"))
        except Exception as exc:
            logger.warning(f"[Scanner] Failed to create scan job row: {exc}")
        return None

    def _update_scan_job(self, job_id: Optional[str], payload: dict[str, Any]) -> None:
        if not job_id:
            return
        try:
            self.db.table("scan_jobs").update(payload).eq("id", job_id).execute()
        except Exception as exc:
            logger.warning(f"[Scanner] Failed to update scan job {job_id}: {exc}")

    def _source_summary_template(self, *, source_key: str, configured: bool, blocked_reason: Optional[str] = None) -> dict[str, Any]:
        next_actions = []
        if blocked_reason == "source_not_configured":
            next_actions.append(f"配置 {source_key} 后再运行扫描。")
        return {
            "source": source_key,
            "configured": configured,
            "status": "blocked" if not configured else "idle",
            "companies_checked": 0,
            "events_found": 0,
            "events_saved": 0,
            "blocked_reason": blocked_reason,
            "next_actions": next_actions,
            "latest_checkpoint": {},
        }

    def _finalize_lane_result(
        self,
        *,
        lane: str,
        source_status: dict[str, dict[str, Any]],
        events: list[ESGEvent],
        blocked_reason: Optional[str],
        next_actions: list[str],
    ) -> dict[str, Any]:
        configured_sources = [item for item in source_status.values() if item.get("configured")]
        any_degraded = any(item.get("status") == "degraded" for item in source_status.values())
        if blocked_reason and not configured_sources and not events:
            status = "blocked"
        elif blocked_reason and not events:
            status = "degraded"
        elif any_degraded and not events:
            status = "degraded"
        else:
            status = "completed"

        checkpoint_state = {
            source: {
                "latest_checkpoint": data.get("latest_checkpoint") or {},
                "companies_checked": data.get("companies_checked", 0),
            }
            for source, data in source_status.items()
        }
        next_cursor = json.dumps(checkpoint_state, ensure_ascii=False) if checkpoint_state else None
        return {
            "lane": lane,
            "status": status,
            "events": events,
            "events_found": len(events),
            "events_saved": 0,
            "blocked_reason": blocked_reason,
            "next_actions": self._dedupe_strings(next_actions),
            "source_status": source_status,
            "checkpoint": checkpoint_state,
            "next_cursor": next_cursor,
        }

    def _fetch_newsapi_articles(self, company_name: str, *, limit: int = 8) -> list[dict[str, Any]]:
        manager = self.data_source_manager
        if not manager.newsapi_key:
            return []
        params = {
            "q": company_name,
            "sortBy": "publishedAt",
            "language": "en",
            "apiKey": manager.newsapi_key,
            "pageSize": limit,
        }
        response = manager._get(manager.newsapi_url, params=params, timeout="news")
        if response.status_code != 200:
            raise RuntimeError(f"NewsAPI returned {response.status_code}")

        articles: list[dict[str, Any]] = []
        for item in response.json().get("articles", []) or []:
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            source_name = str((item.get("source") or {}).get("name") or "").strip()
            published_at = self._isoformat(item.get("publishedAt"))
            if not (url and title and source_name and published_at):
                continue
            articles.append(
                {
                    "title": title,
                    "description": str(item.get("description") or item.get("content") or "").strip(),
                    "url": url,
                    "source": source_name,
                    "published_at": published_at,
                    "company": company_name,
                }
            )
        return articles

    def _fetch_finnhub_articles(self, company_name: str, *, ticker: Optional[str], limit: int = 8) -> list[dict[str, Any]]:
        manager = self.data_source_manager
        if not manager.finnhub_api_key or not ticker:
            return []
        from_date = (datetime.utcnow().date()).replace(day=1).isoformat()
        to_date = datetime.utcnow().date().isoformat()
        response = manager._get(
            f"{manager.finnhub_url}/company-news",
            params={
                "symbol": ticker,
                "from": from_date,
                "to": to_date,
                "token": manager.finnhub_api_key,
            },
            timeout="news",
        )
        if response.status_code != 200:
            raise RuntimeError(f"Finnhub returned {response.status_code}")

        articles: list[dict[str, Any]] = []
        for item in response.json()[:limit]:
            url = str(item.get("url") or "").strip()
            title = str(item.get("headline") or "").strip()
            source_name = str(item.get("source") or "Finnhub").strip()
            published_at = self._isoformat(item.get("datetime"))
            if not (url and title and source_name and published_at):
                continue
            articles.append(
                {
                    "title": title,
                    "description": str(item.get("summary") or "").strip(),
                    "url": url,
                    "source": source_name,
                    "published_at": published_at,
                    "company": company_name,
                    "ticker": ticker,
                }
            )
        return articles

    def _collect_sec_filings(self, company_name: str, *, forms: tuple[str, ...]) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
        manager = self.data_source_manager
        company_ref = manager._resolve_sec_company(company_name)
        if not company_ref:
            return None, []
        submissions = manager._fetch_sec_submissions(company_ref["cik"])
        if not submissions:
            return company_ref, []

        recent = (submissions.get("filings") or {}).get("recent") or {}
        forms_list = recent.get("form") or []
        accessions = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []
        filing_dates = recent.get("filingDate") or []
        items: list[dict[str, Any]] = []
        for form, accession, primary_doc, filed_at in zip(forms_list, accessions, primary_docs, filing_dates):
            normalized_form = str(form or "").upper().strip()
            if normalized_form not in forms:
                continue
            if not accession or not primary_doc or not filed_at:
                continue
            items.append(
                {
                    "company": str(company_ref.get("title") or company_name),
                    "ticker": company_ref.get("ticker"),
                    "cik": company_ref["cik"],
                    "form": normalized_form,
                    "accession_number": accession,
                    "primary_document": primary_doc,
                    "filed_at": self._isoformat(filed_at),
                    "url": manager._filing_document_url(company_ref["cik"], accession, primary_doc),
                    "source": f"SEC {normalized_form}",
                }
            )
        items.sort(key=self._filing_checkpoint_key)
        return company_ref, items

    def _create_news_event(self, article: dict[str, Any]) -> ESGEvent:
        title = str(article.get("title") or "").strip()
        description = str(article.get("description") or "").strip()
        return ESGEvent(
            title=title,
            description=description or title,
            company=str(article.get("company") or "Unknown"),
            event_type=self._classify_event_type(title=title, description=description),
            source=str(article.get("source") or "news"),
            source_url=str(article.get("url") or "").strip() or None,
            detected_at=self._coerce_datetime(article.get("published_at")) or self._utcnow(),
            raw_content=description or title,
        )

    def _create_report_event(self, filing: dict[str, Any]) -> ESGEvent:
        title = f"{filing['company']} filed {filing['form']} with the SEC"
        description = (
            f"SEC filing {filing['form']} was published for {filing['company']} on "
            f"{str(filing.get('filed_at') or '')[:10]}."
        )
        return ESGEvent(
            title=title,
            description=description,
            company=str(filing.get("company") or "Unknown"),
            event_type=self._classify_event_type(
                title=title,
                description=f"{filing.get('form')} {filing.get('source')}",
                default=ESGEventType.OTHER,
            ),
            source="sec_edgar",
            source_url=str(filing.get("url") or "").strip() or None,
            detected_at=self._coerce_datetime(filing.get("filed_at")) or self._utcnow(),
            raw_content=(
                f"SEC {filing.get('form')} accession {filing.get('accession_number')} "
                f"document {filing.get('primary_document')}"
            ),
        )

    def _create_compliance_event(self, filing: dict[str, Any], snippet: str) -> ESGEvent:
        title = f"{filing['company']} disclosed a governance/compliance update via {filing['form']}"
        description = snippet.strip() or f"SEC {filing['form']} disclosed governance or compliance changes."
        return ESGEvent(
            title=title,
            description=description,
            company=str(filing.get("company") or "Unknown"),
            event_type=self._classify_event_type(
                title=title,
                description=description,
                default=ESGEventType.GOVERNANCE_CHANGE,
            ),
            source="sec_edgar",
            source_url=str(filing.get("url") or "").strip() or None,
            detected_at=self._coerce_datetime(filing.get("filed_at")) or self._utcnow(),
            raw_content=description,
        )

    def _scan_news_lane(self, cursor: Optional[str] = None) -> dict[str, Any]:
        tracked_companies = self._get_tracked_companies()
        if not tracked_companies:
            return self._finalize_lane_result(
                lane=self.NEWS_LANE,
                source_status={},
                events=[],
                blocked_reason="tracked_companies_missing",
                next_actions=["先添加关注公司或同步持仓，然后再运行新闻扫描。"],
            )

        source_status = {
            "newsapi": self._source_summary_template(
                source_key="newsapi",
                configured=bool(self.data_source_manager.newsapi_key),
                blocked_reason=None if self.data_source_manager.newsapi_key else "source_not_configured",
            ),
            "finnhub": self._source_summary_template(
                source_key="finnhub",
                configured=bool(self.data_source_manager.finnhub_api_key),
                blocked_reason=None if self.data_source_manager.finnhub_api_key else "source_not_configured",
            ),
        }

        if not any(item["configured"] for item in source_status.values()):
            return self._finalize_lane_result(
                lane=self.NEWS_LANE,
                source_status=source_status,
                events=[],
                blocked_reason="news_sources_unavailable",
                next_actions=["配置 NewsAPI 或 Finnhub 后再运行新闻扫描。"],
            )

        events: list[ESGEvent] = []
        cursor_checkpoint = self._json_loads(cursor)

        for company_name in tracked_companies:
            company_key = self._normalize_company_key(company_name)

            if source_status["newsapi"]["configured"]:
                source_status["newsapi"]["companies_checked"] += 1
                stored_state = self._load_source_state(lane=self.NEWS_LANE, source_key="newsapi", company_key=company_key)
                checkpoint = stored_state.get("checkpoint_value") or cursor_checkpoint.get(company_key) or {}
                try:
                    articles = self._fetch_newsapi_articles(company_name)
                    articles.sort(key=self._news_checkpoint_key)
                    new_articles = [item for item in articles if self._is_new_news_item(item, checkpoint)]
                    for article in new_articles:
                        events.append(self._create_news_event(article))
                    latest_checkpoint = self._news_checkpoint_key(articles[-1]) if articles else None
                    checkpoint_value = (
                        {
                            "published_at": latest_checkpoint[0],
                            "url": latest_checkpoint[1],
                            "title": latest_checkpoint[2],
                        }
                        if latest_checkpoint
                        else checkpoint
                    )
                    source_status["newsapi"]["events_found"] += len(new_articles)
                    source_status["newsapi"]["status"] = "ok" if new_articles else "no_new"
                    source_status["newsapi"]["latest_checkpoint"] = {
                        company_key: checkpoint_value,
                    }
                    self._save_source_state(
                        lane=self.NEWS_LANE,
                        source_key="newsapi",
                        company_key=company_key,
                        checkpoint_value=checkpoint_value,
                        status=source_status["newsapi"]["status"],
                        blocked_reason=None,
                        events_found=len(new_articles),
                        events_saved=0,
                    )
                except Exception as exc:
                    source_status["newsapi"]["status"] = "degraded"
                    source_status["newsapi"]["blocked_reason"] = "newsapi_fetch_failed"
                    source_status["newsapi"]["next_actions"] = self._dedupe_strings(
                        source_status["newsapi"]["next_actions"] + ["检查 NewsAPI key、额度和公司新闻查询结果。"]
                    )
                    logger.warning(f"[Scanner] NewsAPI scan failed for {company_name}: {exc}")

            if source_status["finnhub"]["configured"]:
                source_status["finnhub"]["companies_checked"] += 1
                stored_state = self._load_source_state(lane=self.NEWS_LANE, source_key="finnhub", company_key=company_key)
                checkpoint = stored_state.get("checkpoint_value") or {}
                ticker = self.data_source_manager._resolve_symbol(company_name)
                if not ticker:
                    source_status["finnhub"]["status"] = "degraded"
                    source_status["finnhub"]["blocked_reason"] = "ticker_resolution_failed"
                    source_status["finnhub"]["next_actions"] = self._dedupe_strings(
                        source_status["finnhub"]["next_actions"] + [f"为 {company_name} 补充 ticker 后再运行 Finnhub 新闻扫描。"]
                    )
                    self._save_source_state(
                        lane=self.NEWS_LANE,
                        source_key="finnhub",
                        company_key=company_key,
                        checkpoint_value=checkpoint,
                        status="blocked",
                        blocked_reason="ticker_resolution_failed",
                        events_found=0,
                        events_saved=0,
                    )
                    continue

                try:
                    articles = self._fetch_finnhub_articles(company_name, ticker=ticker)
                    articles.sort(key=self._news_checkpoint_key)
                    new_articles = [item for item in articles if self._is_new_news_item(item, checkpoint)]
                    for article in new_articles:
                        events.append(self._create_news_event(article))
                    latest_checkpoint = self._news_checkpoint_key(articles[-1]) if articles else None
                    checkpoint_value = (
                        {
                            "published_at": latest_checkpoint[0],
                            "url": latest_checkpoint[1],
                            "title": latest_checkpoint[2],
                        }
                        if latest_checkpoint
                        else checkpoint
                    )
                    source_status["finnhub"]["events_found"] += len(new_articles)
                    source_status["finnhub"]["status"] = "ok" if new_articles else "no_new"
                    source_status["finnhub"]["latest_checkpoint"] = {
                        company_key: checkpoint_value,
                    }
                    self._save_source_state(
                        lane=self.NEWS_LANE,
                        source_key="finnhub",
                        company_key=company_key,
                        checkpoint_value=checkpoint_value,
                        status=source_status["finnhub"]["status"],
                        blocked_reason=None,
                        events_found=len(new_articles),
                        events_saved=0,
                    )
                except Exception as exc:
                    source_status["finnhub"]["status"] = "degraded"
                    source_status["finnhub"]["blocked_reason"] = "finnhub_fetch_failed"
                    source_status["finnhub"]["next_actions"] = self._dedupe_strings(
                        source_status["finnhub"]["next_actions"] + ["检查 Finnhub key、额度和 symbol 解析结果。"]
                    )
                    logger.warning(f"[Scanner] Finnhub scan failed for {company_name}: {exc}")

        return self._finalize_lane_result(
            lane=self.NEWS_LANE,
            source_status=source_status,
            events=events,
            blocked_reason=None,
            next_actions=[],
        )

    def _scan_reports_lane(self, cursor: Optional[str] = None) -> dict[str, Any]:
        tracked_companies = self._get_tracked_companies()
        source_status = {
            "sec_edgar": self._source_summary_template(
                source_key="sec_edgar",
                configured=bool(self.data_source_manager.sec_edgar_email),
                blocked_reason=None if self.data_source_manager.sec_edgar_email else "source_not_configured",
            )
        }
        if not tracked_companies:
            return self._finalize_lane_result(
                lane=self.REPORTS_LANE,
                source_status=source_status,
                events=[],
                blocked_reason="tracked_companies_missing",
                next_actions=["先添加关注公司或同步持仓，然后再扫描 SEC 报告。"],
            )
        if not self.data_source_manager.sec_edgar_email:
            return self._finalize_lane_result(
                lane=self.REPORTS_LANE,
                source_status=source_status,
                events=[],
                blocked_reason="sec_edgar_unavailable",
                next_actions=["配置 SEC_EDGAR_EMAIL 后再运行报告扫描。"],
            )

        events: list[ESGEvent] = []
        cursor_checkpoint = self._json_loads(cursor)
        summary = source_status["sec_edgar"]

        for company_name in tracked_companies:
            summary["companies_checked"] += 1
            company_key = self._normalize_company_key(company_name)
            stored_state = self._load_source_state(
                lane=self.REPORTS_LANE,
                source_key="sec_edgar",
                company_key=company_key,
            )
            checkpoint = stored_state.get("checkpoint_value") or cursor_checkpoint.get(company_key) or {}
            company_ref, filings = self._collect_sec_filings(company_name, forms=self.REPORT_FORMS)
            if not company_ref:
                self._save_source_state(
                    lane=self.REPORTS_LANE,
                    source_key="sec_edgar",
                    company_key=company_key,
                    checkpoint_value=checkpoint,
                    status="blocked",
                    blocked_reason="sec_company_not_found",
                    events_found=0,
                    events_saved=0,
                )
                summary["status"] = "degraded"
                summary["blocked_reason"] = "sec_company_resolution_partial"
                summary["next_actions"] = self._dedupe_strings(
                    summary["next_actions"] + [f"检查 {company_name} 的 SEC 公司映射或 ticker。"]
                )
                continue

            new_filings = [item for item in filings if self._is_new_filing(item, checkpoint)]
            for filing in new_filings:
                events.append(self._create_report_event(filing))

            latest_checkpoint = self._filing_checkpoint_key(filings[-1]) if filings else None
            checkpoint_value = (
                {
                    "filed_at": latest_checkpoint[0],
                    "accession_number": latest_checkpoint[1],
                    "form": latest_checkpoint[2],
                }
                if latest_checkpoint
                else checkpoint
            )
            summary["events_found"] += len(new_filings)
            summary["status"] = "ok" if new_filings else ("no_new" if summary["status"] == "idle" else summary["status"])
            summary["latest_checkpoint"] = {company_key: checkpoint_value}
            self._save_source_state(
                lane=self.REPORTS_LANE,
                source_key="sec_edgar",
                company_key=company_key,
                checkpoint_value=checkpoint_value,
                status="ok" if new_filings else "no_new",
                blocked_reason=None,
                events_found=len(new_filings),
                events_saved=0,
            )

        return self._finalize_lane_result(
            lane=self.REPORTS_LANE,
            source_status=source_status,
            events=events,
            blocked_reason=None,
            next_actions=[],
        )

    def _scan_compliance_lane(self, cursor: Optional[str] = None) -> dict[str, Any]:
        tracked_companies = self._get_tracked_companies()
        source_status = {
            "sec_edgar": self._source_summary_template(
                source_key="sec_edgar",
                configured=bool(self.data_source_manager.sec_edgar_email),
                blocked_reason=None if self.data_source_manager.sec_edgar_email else "source_not_configured",
            )
        }
        if not tracked_companies:
            return self._finalize_lane_result(
                lane=self.COMPLIANCE_LANE,
                source_status=source_status,
                events=[],
                blocked_reason="tracked_companies_missing",
                next_actions=["先添加关注公司或同步持仓，然后再运行合规扫描。"],
            )
        if not self.data_source_manager.sec_edgar_email:
            return self._finalize_lane_result(
                lane=self.COMPLIANCE_LANE,
                source_status=source_status,
                events=[],
                blocked_reason="sec_edgar_unavailable",
                next_actions=["配置 SEC_EDGAR_EMAIL 后再运行合规扫描。"],
            )

        events: list[ESGEvent] = []
        cursor_checkpoint = self._json_loads(cursor)
        summary = source_status["sec_edgar"]

        for company_name in tracked_companies:
            summary["companies_checked"] += 1
            company_key = self._normalize_company_key(company_name)
            stored_state = self._load_source_state(
                lane=self.COMPLIANCE_LANE,
                source_key="sec_edgar",
                company_key=company_key,
            )
            checkpoint = stored_state.get("checkpoint_value") or cursor_checkpoint.get(company_key) or {}
            company_ref, filings = self._collect_sec_filings(company_name, forms=self.COMPLIANCE_FORMS)
            if not company_ref:
                self._save_source_state(
                    lane=self.COMPLIANCE_LANE,
                    source_key="sec_edgar",
                    company_key=company_key,
                    checkpoint_value=checkpoint,
                    status="blocked",
                    blocked_reason="sec_company_not_found",
                    events_found=0,
                    events_saved=0,
                )
                summary["status"] = "degraded"
                summary["blocked_reason"] = "sec_company_resolution_partial"
                summary["next_actions"] = self._dedupe_strings(
                    summary["next_actions"] + [f"检查 {company_name} 的 SEC 公司映射或 ticker。"]
                )
                continue

            new_filings = [item for item in filings if self._is_new_filing(item, checkpoint)]
            compliance_found = 0
            for filing in new_filings:
                filing_text = self.data_source_manager._fetch_sec_filing_text(
                    filing["cik"],
                    filing["accession_number"],
                    filing["primary_document"],
                )
                snippet = self.data_source_manager._excerpt_around(filing_text, list(self.COMPLIANCE_KEYWORDS)) if filing_text else None
                if not snippet:
                    continue
                events.append(self._create_compliance_event(filing, snippet))
                compliance_found += 1

            latest_checkpoint = self._filing_checkpoint_key(filings[-1]) if filings else None
            checkpoint_value = (
                {
                    "filed_at": latest_checkpoint[0],
                    "accession_number": latest_checkpoint[1],
                    "form": latest_checkpoint[2],
                }
                if latest_checkpoint
                else checkpoint
            )
            summary["events_found"] += compliance_found
            summary["status"] = "ok" if compliance_found else ("no_new" if summary["status"] == "idle" else summary["status"])
            summary["latest_checkpoint"] = {company_key: checkpoint_value}
            self._save_source_state(
                lane=self.COMPLIANCE_LANE,
                source_key="sec_edgar",
                company_key=company_key,
                checkpoint_value=checkpoint_value,
                status="ok" if compliance_found else "no_new",
                blocked_reason=None,
                events_found=compliance_found,
                events_saved=0,
            )

        return self._finalize_lane_result(
            lane=self.COMPLIANCE_LANE,
            source_status=source_status,
            events=events,
            blocked_reason=None,
            next_actions=[],
        )

    def scan_news_feeds(self, cursor: Optional[str] = None) -> tuple[list[ESGEvent], Optional[str]]:
        lane_result = self._scan_news_lane(cursor)
        self._last_lane_results[self.NEWS_LANE] = lane_result
        return lane_result["events"], lane_result.get("next_cursor")

    def scan_esg_reports(self, cursor: Optional[str] = None) -> tuple[list[ESGEvent], Optional[str]]:
        lane_result = self._scan_reports_lane(cursor)
        self._last_lane_results[self.REPORTS_LANE] = lane_result
        return lane_result["events"], lane_result.get("next_cursor")

    def scan_compliance_updates(self, cursor: Optional[str] = None) -> tuple[list[ESGEvent], Optional[str]]:
        lane_result = self._scan_compliance_lane(cursor)
        self._last_lane_results[self.COMPLIANCE_LANE] = lane_result
        return lane_result["events"], lane_result.get("next_cursor")

    def save_events(self, events: list[ESGEvent]) -> list[str]:
        if not events:
            return []

        saved_ids: list[str] = []
        for event in events:
            if self._existing_event_key(event):
                continue
            try:
                payload = {
                    "title": event.title,
                    "description": event.description,
                    "content": event.description,
                    "company": event.company,
                    "event_type": self._event_type_value(event.event_type),
                    "source": event.source,
                    "source_url": event.source_url,
                    "detected_at": event.detected_at.isoformat(),
                    "raw_content": event.raw_content,
                    "created_at": self._utcnow().isoformat(),
                }
                result = self.db.table("esg_events").insert(payload).execute()
                rows = result.data or []
                if rows:
                    saved_ids.append(str(rows[0]["id"]))
            except Exception as exc:
                logger.warning(f"[Scanner] Failed to save event {event.title}: {exc}")
        return saved_ids

    def get_last_run_summary(self) -> dict[str, Any]:
        return dict(self._last_run_summary)

    def run_scan(self) -> dict[str, Any]:
        logger.info("[Scanner] Starting real-source scan cycle")
        scan_job_id = self._create_scan_job()
        started_at = self._utcnow()

        news_lane = self._scan_news_lane()
        report_lane = self._scan_reports_lane()
        compliance_lane = self._scan_compliance_lane()

        lane_results = {
            self.NEWS_LANE: news_lane,
            self.REPORTS_LANE: report_lane,
            self.COMPLIANCE_LANE: compliance_lane,
        }
        self._last_lane_results = lane_results

        all_saved_ids: list[str] = []
        serialized_lanes: dict[str, Any] = {}
        for lane_name, lane_result in lane_results.items():
            saved_ids = self.save_events(lane_result["events"])
            lane_result["events_saved"] = len(saved_ids)
            for source_summary in lane_result["source_status"].values():
                source_summary["events_saved"] = source_summary.get("events_saved", 0) or source_summary.get("events_found", 0)
                if lane_result["events_saved"] < lane_result["events_found"]:
                    source_summary["next_actions"] = self._dedupe_strings(
                        list(source_summary.get("next_actions") or []) + ["部分事件因去重未重复入库。"]
                    )
            all_saved_ids.extend(saved_ids)
            serialized_lanes[lane_name] = {
                key: value
                for key, value in lane_result.items()
                if key != "events"
            }

        total_events = sum(item["events_found"] for item in lane_results.values())
        total_saved = len(all_saved_ids)
        completed_at = self._utcnow()

        blocked_reasons = [
            item.get("blocked_reason")
            for item in lane_results.values()
            if item.get("blocked_reason")
        ]
        next_actions: list[str] = []
        for item in lane_results.values():
            next_actions.extend(item.get("next_actions") or [])
            for source_summary in item.get("source_status", {}).values():
                next_actions.extend(source_summary.get("next_actions") or [])

        job_status = "completed"
        if blocked_reasons and total_saved == 0:
            job_status = "completed_with_warnings"

        checkpoint_state = {
            lane: lane_result.get("checkpoint") or {}
            for lane, lane_result in lane_results.items()
        }
        scan_job_payload = {
            "status": job_status,
            "completed_at": completed_at.isoformat(),
            "events_found": total_events,
            "events_saved": total_saved,
            "source_summary": serialized_lanes,
            "blocked_reason": blocked_reasons[0] if blocked_reasons else None,
            "next_actions": self._dedupe_strings(next_actions),
            "checkpoint_state": checkpoint_state,
        }
        self._update_scan_job(scan_job_id, scan_job_payload)

        result = {
            "scan_job_id": scan_job_id,
            "total_events": total_events,
            "saved_events": total_saved,
            "event_ids": all_saved_ids,
            "timestamp": completed_at.isoformat(),
            "started_at": started_at.isoformat(),
            "status": job_status,
            "lanes": serialized_lanes,
            "source_summary": serialized_lanes,
            "blocked_reason": blocked_reasons[0] if blocked_reasons else None,
            "next_actions": self._dedupe_strings(next_actions),
            "checkpoint_state": checkpoint_state,
        }
        self._last_run_summary = result
        logger.info(f"[Scanner] Scan complete: {job_status}, found={total_events}, saved={total_saved}")
        return result


_scanner: Optional[Scanner] = None


def get_scanner() -> Scanner:
    global _scanner
    if _scanner is None:
        _scanner = Scanner()
    return _scanner
