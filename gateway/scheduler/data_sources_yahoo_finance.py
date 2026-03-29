# data_sources_yahoo_finance.py — Yahoo Finance Real Time (RapidAPI) 版本
# 这是对gateway/scheduler/data_sources.py的修改示例
# 只需替换其中的两个方法即可

# 将这些代码替换到 data_sources.py 中对应的位置

import os
import requests
from typing import Optional, Dict, Any
from gateway.utils.logger import get_logger
from gateway.utils.cache import get_cache, set_cache
from gateway.utils.retry import retry_with_backoff

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 修改1: 更新 DataSourceManager.__init__() 方法
# ════════════════════════════════════════════════════════════════════════════

# 【原代码】
"""
def __init__(self):
    self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    self.hyfinnan_api_key = os.getenv("HYFINNAN_API_KEY", "")
    ...
"""

# 【新代码】替换为：
class DataSourceManagerPatched:
    def __init__(self):
        """初始化数据源管理器 - Yahoo Finance版本"""
        self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")

        # ✨ 替换 Hyfinnan 为 RapidAPI Yahoo Finance
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
        self.rapidapi_host = os.getenv("RAPIDAPI_HOST", "yh-finance.p.rapidapi.com")

        self.sec_edgar_email = os.getenv("SEC_EDGAR_EMAIL", "")
        self.newsapi_key = os.getenv("NEWSAPI_KEY", "")
        self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")

        self.alpha_vantage_url = "https://www.alphavantage.co/query"
        self.newsapi_url = "https://newsapi.org/v2/everything"
        self.finnhub_url = "https://finnhub.io/api/v1"
        self.rapidapi_base_url = f"https://{self.rapidapi_host}"

        self.cache_ttl_hours = 24

        logger.info("[DataSourceManager] Initialized with Yahoo Finance Real Time API (RapidAPI)")


# ════════════════════════════════════════════════════════════════════════════
# 修改2: 替换 _call_hyfinnan_esg_api() 为 Yahoo Finance
# ════════════════════════════════════════════════════════════════════════════

def _call_yahoo_finance_api(self, ticker: str) -> Optional[Dict[str, Any]]:
    """
    ✨ 新方法：调用 RapidAPI Yahoo Finance API
    替代原有的 _call_hyfinnan_esg_api()

    Args:
        ticker: 股票代码 (如 "TSLA", "AAPL")

    Returns:
        企业基本信息和财务数据
    """
    if not self.rapidapi_key:
        logger.warning("[DataSourceManager] RapidAPI key not configured")
        return None

    try:
        # Yahoo Finance API 端点
        url = f"{self.rapidapi_base_url}/v10/finance/quoteSummary/{ticker}"

        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": self.rapidapi_host,
            "Accept": "application/json"
        }

        params = {
            "modules": "summaryProfile,assetProfile,financialData,earnings,defaultKeyStatistics"
        }

        logger.info(f"[DataSourceManager] Fetching Yahoo Finance data for {ticker}")
        resp = requests.get(url, headers=headers, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()

            # 解析 Yahoo Finance 响应
            if "quoteSummary" in data and data["quoteSummary"]["result"]:
                quote = data["quoteSummary"]["result"][0]

                # 提取关键数据
                summary = quote.get("summaryProfile", {})
                asset = quote.get("assetProfile", {})
                financial = quote.get("financialData", {})
                stats = quote.get("defaultKeyStatistics", {})

                parsed_data = {
                    # 企业基本信息
                    "company_name": summary.get("longName") or asset.get("longName"),
                    "industry": asset.get("industry"),
                    "sector": asset.get("sector"),
                    "employees": asset.get("fullTimeEmployees"),
                    "website": asset.get("website"),
                    "description": summary.get("longBusinessSummary"),

                    # 财务数据
                    "market_cap": financial.get("marketCap"),
                    "total_revenue": financial.get("totalRevenue"),
                    "total_debt": financial.get("totalDebt"),
                    "total_cash": financial.get("totalCash"),
                    "free_cashflow": financial.get("freeCashflow"),
                    "operating_cashflow": financial.get("operatingCashflow"),
                    "profit_margin": financial.get("profitMargins"),
                    "return_on_assets": financial.get("returnOnAssets"),
                    "return_on_equity": financial.get("returnOnEquity"),

                    # 估值指标
                    "pe_ratio": stats.get("trailingPE"),
                    "pb_ratio": stats.get("priceToBook"),
                    "dividend_yield": financial.get("dividendYield"),
                    "payout_ratio": stats.get("payoutRatio"),

                    # ESG相关（Yahoo Finance有限的ESG数据）
                    "sustainability_score": financial.get("sustainabilityScore"),
                }

                logger.info(f"[DataSourceManager] Successfully fetched data for {ticker}")
                return parsed_data

            else:
                logger.warning(f"[DataSourceManager] No data returned for {ticker}")
                return None

        else:
            logger.warning(f"[DataSourceManager] Yahoo Finance API error: {resp.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        logger.warning(f"[DataSourceManager] Yahoo Finance request error: {e}")
        return None

    except Exception as e:
        logger.error(f"[DataSourceManager] Unexpected error: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# 修改3: 更新 fetch_company_data() 集成新的Yahoo Finance调用
# ════════════════════════════════════════════════════════════════════════════

# 在 fetch_company_data() 方法中，替换原有的Hyfinnan调用
# 原代码:
"""
def fetch_company_data(self, company_name: str, ticker: Optional[str] = None, ...):
    ...
    company_data.environmental = self.fetch_esg_environmental(company_name)
    company_data.social = self.fetch_esg_social(company_name)
    company_data.governance = self.fetch_esg_governance(company_name)
    company_data.external_ratings = self.fetch_external_esg_ratings(company_name)
    ...
"""

# 新代码 - 添加Yahoo Finance数据拉取:
def fetch_company_data_enhanced(self, company_name: str, ticker: Optional[str] = None, ...):
    """
    增强版：集成Yahoo Finance数据
    """
    company_data = CompanyData(
        company_name=company_name,
        ticker=ticker,
        industry=industry,
        last_updated=datetime.now()
    )

    try:
        # 1. 优先使用Yahoo Finance获取基础财务数据
        if ticker:
            logger.info(f"[DataSourceManager] Fetching Yahoo Finance data for {ticker}")
            yahoo_data = self._call_yahoo_finance_api(ticker)
            if yahoo_data:
                company_data.financial = yahoo_data
                # 同时更新企业信息
                company_data.industry = yahoo_data.get("industry")

        # 2. Alpha Vantage补充数据
        company_data.financial.update(
            self.fetch_from_alpha_vantage(ticker or company_name)
        )

        # 3. ESG数据（从其他来源）
        company_data.environmental = self.fetch_esg_environmental(company_name)
        company_data.social = self.fetch_esg_social(company_name)
        company_data.governance = self.fetch_esg_governance(company_name)

        # 4. 外部评分
        company_data.external_ratings = self.fetch_external_esg_ratings(company_name)

        # 5. 新闻数据
        company_data.recent_news = self.fetch_recent_news(company_name, limit=10)

        company_data.data_sources = [
            "yahoo_finance",      # ✨ 新增
            "alpha_vantage",
            "sec_edgar",
            "newsapi",
            "finnhub"
        ]

        logger.info(f"[DataSourceManager] Successfully fetched all data for {company_name}")
        return company_data

    except Exception as e:
        logger.error(f"[DataSourceManager] Error: {e}")
        return company_data


# ════════════════════════════════════════════════════════════════════════════
# 修改4: 修改 fetch_esg_* 方法以支持Yahoo Finance
# ════════════════════════════════════════════════════════════════════════════

def fetch_esg_environmental_enhanced(self, company_name: str) -> Dict[str, Any]:
    """
    ✨ 更新版：结合Yahoo Finance和其他源拉取环保数据
    """
    cache_key = f"esg_env_{company_name}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        data = {
            "carbon_emissions": None,
            "carbon_intensity": None,
            "renewable_energy_percentage": None,
            "water_consumption": None,
            "waste_recycling_rate": None,
            "energy_efficiency_index": None,
            "environmental_compliance": None,
            "data_source": "combined"
        }

        # 尝试多个来源
        # 1. SEC EDGAR (10-K报告中的环保信息)
        if self.sec_edgar_email:
            sec_data = self._fetch_from_sec_edgar(company_name)
            if sec_data:
                data.update(sec_data)
                data["data_source"] = "SEC EDGAR"

        # 2. 新闻API可能有环保相关信息
        news = self.fetch_recent_news(company_name, limit=5)
        if any("carbon" in n.get("title", "").lower() or "env" in n.get("title", "").lower()
               for n in news):
            data["has_recent_env_news"] = True

        set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
        return data

    except Exception as e:
        logger.warning(f"[DataSourceManager] Environmental data error: {e}")
        return {}


# ════════════════════════════════════════════════════════════════════════════
# 配置更新说明
# ════════════════════════════════════════════════════════════════════════════

"""
📝 .env 文件更新

【删除】:
HYFINNAN_API_KEY=xxxxx

【添加】:
RAPIDAPI_KEY=your-rapidapi-key-here
RAPIDAPI_HOST=yh-finance.p.rapidapi.com

获取RapidAPI Key:
1. 访问 https://rapidapi.com/spartan737/api/yh-finance
2. 点击 "Subscribe"
3. 复制你的 API Key
4. 填入.env中的 RAPIDAPI_KEY
"""

# ════════════════════════════════════════════════════════════════════════════
# 测试脚本
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 快速测试
    import sys
    sys.path.insert(0, "/path/to/gateway")

    from gateway.scheduler.data_sources import DataSourceManager

    # 初始化
    mgr = DataSourceManager()

    # 测试1: Yahoo Finance API
    print("Test 1: Yahoo Finance API")
    yahoo_data = mgr._call_yahoo_finance_api("TSLA")
    if yahoo_data:
        print(f"✓ 成功获取数据: {list(yahoo_data.keys())}")
        print(f"  - 公司: {yahoo_data.get('company_name')}")
        print(f"  - 市值: {yahoo_data.get('market_cap')}")
    else:
        print("✗ 获取失败，检查RAPIDAPI_KEY配置")

    # 测试2: 完整数据拉取
    print("\nTest 2: Complete data fetch")
    company_data = mgr.fetch_company_data("Tesla", ticker="TSLA")
    print(f"✓ 财务数据来源: {company_data.data_sources}")
    print(f"  - 包含财务数据: {bool(company_data.financial)}")
    print(f"  - 包含环保数据: {bool(company_data.environmental)}")
    print(f"  - 包含新闻: {len(company_data.recent_news)} 条")

    print("\n✓ 测试完成！")
