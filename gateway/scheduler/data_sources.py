# data_sources.py — 多源数据集成管理器
# 职责：集成 Alpha Vantage、Hyfinnan、SEC EDGAR、新闻API等数据源
# 统一的数据模型和拉取接口

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import requests
from gateway.utils.logger import get_logger
from gateway.utils.cache import get_cache, set_cache
from gateway.utils.retry import retry_with_backoff

logger = get_logger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────────────────

class CompanyData(BaseModel):
    """企业完整数据模型"""
    company_name: str
    ticker: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    employees: Optional[int] = None

    # ESG相关数据
    environmental: Dict[str, Any] = {}
    social: Dict[str, Any] = {}
    governance: Dict[str, Any] = {}

    # 财务数据
    financial: Dict[str, Any] = {}

    # 外部评分
    external_ratings: Dict[str, Any] = {}

    # 新闻事件
    recent_news: List[Dict[str, Any]] = []

    # 数据来源和时间戳
    data_sources: List[str] = []
    last_updated: datetime = None
    historical_data: Optional[Dict[str, Any]] = None


# ── 数据源管理器 ────────────────────────────────────────────────────────────

class DataSourceManager:
    """
    多源数据集成管理器
    负责从各个 API 拉取数据并统一格式
    """

    def __init__(self):
        """初始化数据源管理器"""
        self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        self.hyfinnan_api_key = os.getenv("HYFINNAN_API_KEY", "")
        self.sec_edgar_email = os.getenv("SEC_EDGAR_EMAIL", "")
        self.newsapi_key = os.getenv("NEWSAPI_KEY", "")
        self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")

        self.alpha_vantage_url = "https://www.alphavantage.co/query"
        self.newsapi_url = "https://newsapi.org/v2/everything"
        self.finnhub_url = "https://finnhub.io/api/v1"

        self.cache_ttl_hours = 24

    def fetch_company_data(self, company_name: str, ticker: Optional[str] = None,
                          industry: Optional[str] = None) -> CompanyData:
        """
        综合拉取企业的所有相关数据

        Args:
            company_name: 公司名称
            ticker: 股票代码（可选）
            industry: 行业分类（可选）

        Returns:
            CompanyData: 包含所有数据源信息的企业数据
        """
        logger.info(f"[DataSourceManager] Fetching data for {company_name}")

        company_data = CompanyData(
            company_name=company_name,
            ticker=ticker,
            industry=industry,
            last_updated=datetime.now()
        )

        try:
            # 并行拉取各数据源（实际应使用asyncio并发）
            company_data.financial = self.fetch_from_alpha_vantage(ticker or company_name)
            company_data.environmental = self.fetch_esg_environmental(company_name)
            company_data.social = self.fetch_esg_social(company_name)
            company_data.governance = self.fetch_esg_governance(company_name)
            company_data.external_ratings = self.fetch_external_esg_ratings(company_name)
            company_data.recent_news = self.fetch_recent_news(company_name, limit=10)

            company_data.data_sources = [
                "alpha_vantage",
                "hyfinnan",
                "sec_edgar",
                "newsapi",
                "finnhub"
            ]

            logger.info(f"[DataSourceManager] Successfully fetched data for {company_name}")
            return company_data

        except Exception as e:
            logger.error(f"[DataSourceManager] Error fetching data: {e}")
            # 返回部分数据而不是完全失败
            return company_data

    @retry_with_backoff(max_retries=3)
    def fetch_from_alpha_vantage(self, ticker: str) -> Dict[str, Any]:
        """
        从 Alpha Vantage API 拉取财务和股价数据

        支持的数据类型：
        - 股价数据（日、周、月）
        - 基本信息（市值、EPS、PE等）
        - 技术指标
        """
        cache_key = f"av_financial_{ticker}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        try:
            data = {}

            # 获取公司基本信息
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": ticker,
                "apikey": self.alpha_vantage_api_key
            }
            resp = requests.get(self.alpha_vantage_url, params=params, timeout=10)
            if resp.status_code == 200:
                quote = resp.json().get("Global Quote", {})
                data.update({
                    "stock_price": quote.get("05. price"),
                    "market_cap": quote.get("n/a"),  # 需要额外调用获取
                    "pe_ratio": quote.get("n/a"),
                    "dividend_yield": quote.get("n/a"),
                    "52_week_high": quote.get("n/a"),
                    "52_week_low": quote.get("n/a"),
                })

            # 获取年度收入和利润数据
            params["function"] = "INCOME_STATEMENT"
            resp = requests.get(self.alpha_vantage_url, params=params, timeout=10)
            if resp.status_code == 200:
                annual_reports = resp.json().get("annualReports", [])
                if annual_reports:
                    latest = annual_reports[0]
                    data.update({
                        "total_revenue": float(latest.get("totalRevenue", 0)),
                        "gross_profit": float(latest.get("grossProfit", 0)),
                        "operating_income": float(latest.get("operatingIncome", 0)),
                        "net_income": float(latest.get("netIncome", 0)),
                    })

            # 获取现金流
            params["function"] = "CASH_FLOW"
            resp = requests.get(self.alpha_vantage_url, params=params, timeout=10)
            if resp.status_code == 200:
                annual_reports = resp.json().get("annualReports", [])
                if annual_reports:
                    latest = annual_reports[0]
                    data.update({
                        "operating_cash_flow": float(latest.get("operatingCashFlow", 0)),
                        "capital_expenditure": float(latest.get("capitalExpenditure", 0)),
                    })

            set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
            return data

        except Exception as e:
            logger.warning(f"[DataSourceManager] Alpha Vantage error for {ticker}: {e}")
            return {}

    def fetch_esg_environmental(self, company_name: str) -> Dict[str, Any]:
        """
        拉取环境相关ESG数据
        来源：Hyfinnan API、SEC EDGAR、Refinitiv等
        """
        cache_key = f"esg_env_{company_name}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        try:
            data = {
                "carbon_emissions": None,  # tCO2e
                "carbon_intensity": None,  # tCO2e/百万收入
                "renewable_energy_percentage": None,
                "water_consumption": None,  # 千升
                "waste_recycling_rate": None,
                "energy_efficiency_index": None,
                "environmental_compliance": None,
            }

            # 调用 Hyfinnan API（如果可用）
            if self.hyfinnan_api_key:
                esg_data = self._call_hyfinnan_esg_api(company_name, "environmental")
                if esg_data:
                    data.update(esg_data)

            set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
            return data

        except Exception as e:
            logger.warning(f"[DataSourceManager] Environmental ESG error: {e}")
            return {}

    def fetch_esg_social(self, company_name: str) -> Dict[str, Any]:
        """
        拉取社会相关ESG数据
        包含：员工满意度、多样性、供应链伦理等
        """
        cache_key = f"esg_social_{company_name}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        try:
            data = {
                "employee_satisfaction_score": None,
                "employee_turnover_rate": None,
                "women_percentage_total": None,
                "women_percentage_management": None,
                "minorities_percentage": None,
                "diversity_initiatives": [],
                "supply_chain_audits": None,
                "supply_chain_compliance_rate": None,
                "community_investment": None,
                "customer_satisfaction": None,
                "data_breach_incidents": None,
            }

            # 从 Hyfinnan 拉取社会评分
            if self.hyfinnan_api_key:
                esg_data = self._call_hyfinnan_esg_api(company_name, "social")
                if esg_data:
                    data.update(esg_data)

            set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
            return data

        except Exception as e:
            logger.warning(f"[DataSourceManager] Social ESG error: {e}")
            return {}

    def fetch_esg_governance(self, company_name: str) -> Dict[str, Any]:
        """
        拉取治理相关ESG数据
        包含：董事会结构、薪酬透明度、反腐等
        """
        cache_key = f"esg_gov_{company_name}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        try:
            data = {
                "board_size": None,
                "independent_directors_percentage": None,
                "women_directors_percentage": None,
                "ceo_duality": None,  # CEO是否同时担任董事长
                "ceo_to_median_pay_ratio": None,
                "executive_pay_peer_comparison": None,
                "anti_corruption_policy": None,
                "whistleblower_program": None,
                "corruption_violations": [],
                "audit_committee_effectiveness": None,
                "shareholder_voting_rights": None,
            }

            # 从 SEC EDGAR 拉取治理信息（如果可用）
            if self.sec_edgar_email:
                gov_data = self._fetch_from_sec_edgar(company_name)
                if gov_data:
                    data.update(gov_data)

            # 从 Hyfinnan 拉取治理评分
            if self.hyfinnan_api_key:
                esg_data = self._call_hyfinnan_esg_api(company_name, "governance")
                if esg_data:
                    data.update(esg_data)

            set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
            return data

        except Exception as e:
            logger.warning(f"[DataSourceManager] Governance ESG error: {e}")
            return {}

    def fetch_external_esg_ratings(self, company_name: str) -> Dict[str, Any]:
        """
        拉取第三方ESG评级
        包括：MSCI、Sustainalytics、Refinitiv等
        """
        cache_key = f"esg_ratings_{company_name}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        try:
            data = {
                "msci_rating": None,  # AAA-CCC
                "msci_score": None,  # 0-100
                "sustainalytics_score": None,  # 0-100
                "refinitiv_score": None,  # 0-100
                "bloomberg_esg_score": None,
                "cdp_climate_score": None,
                "ftse4good_included": None,
            }

            # 这部分通常需要付费API，这里预留接口
            if self.hyfinnan_api_key:
                ratings = self._call_hyfinnan_ratings_api(company_name)
                if ratings:
                    data.update(ratings)

            set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
            return data

        except Exception as e:
            logger.warning(f"[DataSourceManager] External ratings error: {e}")
            return {}

    @retry_with_backoff(max_retries=3)
    def fetch_recent_news(self, company_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        从 NewsAPI 和 Finnhub 拉取最近的新闻
        """
        cache_key = f"news_{company_name}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        try:
            news_list = []

            # 使用 NewsAPI
            if self.newsapi_key:
                params = {
                    "q": company_name,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "apiKey": self.newsapi_key,
                    "pageSize": limit,
                }
                resp = requests.get(self.newsapi_url, params=params, timeout=10)
                if resp.status_code == 200:
                    articles = resp.json().get("articles", [])
                    for article in articles:
                        news_list.append({
                            "title": article.get("title"),
                            "description": article.get("description"),
                            "url": article.get("url"),
                            "source": article.get("source", {}).get("name"),
                            "published_at": article.get("publishedAt"),
                            "content": article.get("content"),
                        })

            set_cache(cache_key, news_list, ttl_hours=6)  # 新闻缓存6小时
            return news_list

        except Exception as e:
            logger.warning(f"[DataSourceManager] News fetch error: {e}")
            return []

    def _call_hyfinnan_esg_api(self, company_name: str, category: str) -> Optional[Dict[str, Any]]:
        """
        调用 Hyfinnan ESG API
        需要先获取 API Key：https://www.hyfinnan.com
        """
        if not self.hyfinnan_api_key:
            return None

        try:
            # 这是示例实现，实际URL和参数需要根据Hyfinnan的API文档调整
            url = f"https://api.hyfinnan.com/v1/esg/{company_name}"
            headers = {"Authorization": f"Bearer {self.hyfinnan_api_key}"}
            params = {"category": category}

            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()

        except Exception as e:
            logger.warning(f"[DataSourceManager] Hyfinnan API error: {e}")

        return None

    def _call_hyfinnan_ratings_api(self, company_name: str) -> Optional[Dict[str, Any]]:
        """调用 Hyfinnan 评级API"""
        if not self.hyfinnan_api_key:
            return None

        try:
            url = f"https://api.hyfinnan.com/v1/ratings/{company_name}"
            headers = {"Authorization": f"Bearer {self.hyfinnan_api_key}"}

            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()

        except Exception as e:
            logger.warning(f"[DataSourceManager] Hyfinnan Ratings error: {e}")

        return None

    def _fetch_from_sec_edgar(self, company_name: str) -> Optional[Dict[str, Any]]:
        """
        从 SEC EDGAR 拉取公司披露信息
        主要用于获取 10-K（年报）、DEF 14A（代理声明）等
        """
        if not self.sec_edgar_email:
            return None

        try:
            # SEC EDGAR API 示例
            search_url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "company": company_name,
                "action": "getcompany",
                "count": 1,
            }

            resp = requests.get(search_url, params=params, timeout=10,
                              headers={"User-Agent": self.sec_edgar_email})

            # 解析响应（实际实现会更复杂）
            if resp.status_code == 200:
                # 这里应该解析HTML或使用SEC的JSON API
                # 为简化示例，返回None
                pass

        except Exception as e:
            logger.warning(f"[DataSourceManager] SEC EDGAR error: {e}")

        return None

    def sync_company_snapshot(self, company_name: str, ticker: Optional[str] = None,
                            industry: Optional[str] = None) -> bool:
        """
        同步公司数据快照到数据库缓存
        用于定期更新和数据持久化
        """
        try:
            company_data = self.fetch_company_data(company_name, ticker, industry)

            # 这里应该将数据保存到数据库
            # 使用 Supabase client
            from gateway.db.supabase_client import supabase_client

            supabase_client.table("company_data_snapshot").insert({
                "company_name": company_name,
                "ticker": ticker,
                "esg_data": company_data.dict(),
                "snapshot_date": datetime.now().date().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }).execute()

            logger.info(f"[DataSourceManager] Synced snapshot for {company_name}")
            return True

        except Exception as e:
            logger.error(f"[DataSourceManager] Sync error: {e}")
            return False
