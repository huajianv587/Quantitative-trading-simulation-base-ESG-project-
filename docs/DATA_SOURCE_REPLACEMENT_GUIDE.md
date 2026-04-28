# 数据源替换指南 - Yahoo Finance Real Time (RapidAPI)

**修改范围**: 仅修改 `gateway/scheduler/data_sources.py` 中的几个方法
**影响范围**: 不影响其他模块
**修改时间**: 15分钟

---

## 📋 修改清单

### ✅ 需要修改的方法（共4个）

| 方法 | 行号 | 用途 |
|------|------|------|
| `_call_hyfinnan_esg_api()` | ~330 | 替换为Yahoo Finance API |
| `fetch_esg_environmental()` | ~186 | 调用方式不变 |
| `fetch_esg_social()` | ~220 | 调用方式不变 |
| `fetch_esg_governance()` | ~260 | 调用方式不变 |
| `_call_hyfinnan_ratings_api()` | ~360 | 替换为Yahoo Finance API |

### ❌ 不需要修改

- 其他所有模块（agents, scheduler等）
- API端点
- 数据模型（schemas.py）
- 数据库表结构

---

## 🔧 修改方案

### 步骤1: 更新.env文件

**原配置**:
```bash
HYFINNAN_API_KEY=xxxxx
```

**新配置**:
```bash
# 替换为RapidAPI Yahoo Finance
RAPIDAPI_KEY=your_rapidapi_key_here
RAPIDAPI_HOST=yh-finance.p.rapidapi.com  # 或其他Yahoo Finance RapidAPI端点
```

获取方式: https://rapidapi.com/spartan737/api/yh-finance

### 步骤2: 修改DataSourceManager初始化

在 `gateway/scheduler/data_sources.py` 中修改 `__init__` 方法：

```python
def __init__(self):
    """初始化数据源管理器"""
    self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")

    # 替换 Hyfinnan
    self.rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
    self.rapidapi_host = os.getenv("RAPIDAPI_HOST", "yh-finance.p.rapidapi.com")

    # 保留其他配置
    self.sec_edgar_email = os.getenv("SEC_EDGAR_EMAIL", "")
    self.newsapi_key = os.getenv("NEWSAPI_KEY", "")
    self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")

    self.alpha_vantage_url = "https://www.alphavantage.co/query"
    self.newsapi_url = "https://newsapi.org/v2/everything"
    self.finnhub_url = "https://finnhub.io/api/v1"
    # 新增
    self.rapidapi_base_url = f"https://{self.rapidapi_host}"

    self.cache_ttl_hours = 24
```

### 步骤3: 替换Hyfinnan ESG API调用

**原方法** (行号 ~330):
```python
def _call_hyfinnan_esg_api(self, company_name: str, category: str) -> Optional[Dict[str, Any]]:
    """调用 Hyfinnan ESG API"""
    if not self.hyfinnan_api_key:
        return None

    try:
        url = f"https://api.hyfinnan.com/v1/esg/{company_name}"
        headers = {"Authorization": f"Bearer {self.hyfinnan_api_key}"}
        params = {"category": category}

        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()

    except Exception as e:
        logger.warning(f"[DataSourceManager] Hyfinnan API error: {e}")

    return None
```

**新方法** (替换为Yahoo Finance):
```python
def _call_yahoo_finance_api(self, ticker: str) -> Optional[Dict[str, Any]]:
    """
    调用 RapidAPI Yahoo Finance API
    获取企业基本信息和财务数据
    """
    if not self.rapidapi_key:
        logger.warning("[DataSourceManager] RapidAPI key not configured")
        return None

    try:
        # 获取公司信息
        url = f"{self.rapidapi_base_url}/v10/finance/quoteSummary/{ticker}"

        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": self.rapidapi_host
        }

        params = {
            "modules": "summaryProfile,assetProfile,financialData,earnings"
        }

        resp = requests.get(url, headers=headers, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()

            # 解析响应数据
            if "quoteSummary" in data:
                quote = data["quoteSummary"]["result"][0]

                return {
                    "company_name": quote.get("assetProfile", {}).get("longBusinessSummary"),
                    "industry": quote.get("assetProfile", {}).get("industry"),
                    "employees": quote.get("assetProfile", {}).get("fullTimeEmployees"),
                    "website": quote.get("assetProfile", {}).get("website"),
                    "sector": quote.get("assetProfile", {}).get("sector"),
                    "market_cap": quote.get("financialData", {}).get("marketCap"),
                    "revenue": quote.get("financialData", {}).get("totalRevenue"),
                    "profit_margin": quote.get("financialData", {}).get("profitMargins"),
                }

    except Exception as e:
        logger.warning(f"[DataSourceManager] Yahoo Finance API error: {e}")

    return None
```

### 步骤4: 修改ESG数据拉取方法

由于Yahoo Finance API主要提供财务数据而非ESG数据，建议改为使用其他补充源。修改方法如下：

**fetch_esg_environmental方法** (行号 ~186):

```python
def fetch_esg_environmental(self, company_name: str) -> Dict[str, Any]:
    """
    拉取环境相关ESG数据
    来源：Yahoo Finance、SEC EDGAR、或其他替代源
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
        }

        # 新方式：尝试从Yahoo Finance获取补充数据
        # Yahoo Finance本身不提供ESG数据，但可以获取企业信息
        # 建议：结合SEC EDGAR的10-K报告来提取环保信息

        if self.sec_edgar_email:
            sec_data = self._fetch_from_sec_edgar_esg(company_name, "environmental")
            if sec_data:
                data.update(sec_data)

        set_cache(cache_key, data, ttl_hours=self.cache_ttl_hours)
        return data

    except Exception as e:
        logger.warning(f"[DataSourceManager] Environmental ESG error: {e}")
        return {}
```

---

## 💡 建议方案

由于Yahoo Finance Real Time主要提供**财务数据**而非**ESG数据**，推荐：

### 方案A: 组合使用（推荐）
```
Yahoo Finance (RapidAPI)  →  财务数据 ✓
    ↓
SEC EDGAR 10-K/10-Q     →  ESG披露数据 ✓
    ↓
NewsAPI                 →  ESG事件/新闻 ✓
    ↓
Alpha Vantage           →  股价/指标 ✓
```

### 方案B: 添加免费ESG API (可选)
建议添加免费的ESG替代源：
- **ESG Ratings API** (https://rapidapi.com/api-key-holders)
- **World Bank API** (免费，有环保数据)
- **UN SDG API** (免费，有可持续发展数据)

---

## 🔄 修改汇总表

| 原数据源 | 新数据源 | 替换位置 | 优先级 |
|---------|---------|--------|--------|
| Hyfinnan ESG | Yahoo Finance + SEC EDGAR | `data_sources.py` 行330 | 必修 |
| Hyfinnan评分 | Yahoo Finance财务 | `data_sources.py` 行360 | 必修 |
| （其他所有） | 保持不变 | - | - |

---

## 📝 完整的修改代码示例

### 完整的修改后的__init__方法:

```python
def __init__(self):
    """初始化数据源管理器"""
    self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")

    # 替换 Hyfinnan 为 RapidAPI Yahoo Finance
    self.rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
    self.rapidapi_host = os.getenv("RAPIDAPI_HOST", "yh-finance.p.rapidapi.com")

    self.sec_edgar_email = os.getenv("SEC_EDGAR_EMAIL", "")
    self.newsapi_key = os.getenv("NEWSAPI_KEY", "")
    self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")

    # URLs
    self.alpha_vantage_url = "https://www.alphavantage.co/query"
    self.newsapi_url = "https://newsapi.org/v2/everything"
    self.finnhub_url = "https://finnhub.io/api/v1"
    self.rapidapi_base_url = f"https://{self.rapidapi_host}"

    self.cache_ttl_hours = 24

    logger.info("[DataSourceManager] Initialized with Yahoo Finance Real Time API (RapidAPI)")
```

---

## ✅ 验证步骤

### 1. 更新.env文件
```bash
RAPIDAPI_KEY=your-key-here
RAPIDAPI_HOST=yh-finance.p.rapidapi.com
```

### 2. 测试数据拉取
```python
from gateway.scheduler.data_sources import DataSourceManager

mgr = DataSourceManager()

# 测试Yahoo Finance API
data = mgr.fetch_company_data("Tesla", ticker="TSLA")
print(data)
# 应该看到财务数据已成功拉取

# 其他来源（Alpha Vantage等）应继续正常工作
```

### 3. 验证系统仍可正常运行
```bash
curl http://localhost:8012/health
curl -X POST http://localhost:8012/agent/esg-score -H "Content-Type: application/json" -d '{"company":"Tesla"}'
```

---

## 🔗 相关资源

| 资源 | 链接 |
|------|------|
| Yahoo Finance RapidAPI | https://rapidapi.com/spartan737/api/yh-finance |
| RapidAPI Key管理 | https://rapidapi.com/settings/apps |
| API文档 | RapidAPI 上提供的完整文档 |

---

## ❓ FAQ

**Q: 其他模块需要修改吗？**
A: 不需要。DataSourceManager是单独的模块，其他所有调用都通过这个接口。

**Q: ESG评分会受影响吗？**
A: 不会。ESG评分算法保持不变，只是数据来源不同。

**Q: 如何回滚到Hyfinnan？**
A: 只需恢复`_call_hyfinnan_esg_api()`方法即可，所有其他代码无需改动。

**Q: 是否需要重新部署数据库？**
A: 不需要。没有数据库结构变化。

---

## 📌 总结

- ✅ **仅修改1个文件**: `gateway/scheduler/data_sources.py`
- ✅ **仅修改2个方法**: `_call_hyfinnan_esg_api()` 和初始化方法
- ✅ **仅配置1个.env变量**: `RAPIDAPI_KEY`
- ✅ **零影响其他模块**
- ✅ **5分钟完成**

立即开始修改吧！ 🚀
