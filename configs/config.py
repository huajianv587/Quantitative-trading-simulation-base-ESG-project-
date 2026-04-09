import os
from dotenv import load_dotenv

load_dotenv()


def _first_env(*names: str, default: str = "") -> str:
    """Return the first non-empty env var value from the provided aliases."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _env_int(*names: str, default: int) -> int:
    value = _first_env(*names, default=str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_bool(*names: str, default: bool) -> bool:
    value = _first_env(*names, default=str(default))
    return str(value).lower() in {"1", "true", "yes", "on"}


def _env_choice(*names: str, default: str, allowed: set[str]) -> str:
    value = _first_env(*names, default=default).strip().lower()
    return value if value in allowed else default


class Settings:
    def __init__(self):
        # ── Runtime mode ───────────────────────────────────────────────
        self.APP_MODE = _env_choice(
            "APP_MODE",
            default="local",
            allowed={"local", "hybrid", "prod"},
        )
        self.LLM_BACKEND_MODE = _env_choice(
            "LLM_BACKEND_MODE",
            default="auto",
            allowed={"auto", "local", "remote", "cloud"},
        )

        # ── LLM APIs ───────────────────────────────────────────────────
        self.OPENAI_API_KEY = _first_env("OPENAI_API_KEY")
        self.ANTHROPIC_API_KEY = _first_env("ANTHROPIC_API_KEY")
        self.DEEPSEEK_API_KEY = _first_env("DEEPSEEK_API_KEY")
        self.REMOTE_LLM_URL = _first_env("REMOTE_LLM_URL")
        self.REMOTE_LLM_API_KEY = _first_env("REMOTE_LLM_API_KEY")
        self.REMOTE_LLM_TIMEOUT = _env_int("REMOTE_LLM_TIMEOUT", default=180)

        # ── AWS (for data sources) ─────────────────────────────────────
        self.AWS_ACCESS_KEY_ID = _first_env("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = _first_env("AWS_SECRET_ACCESS_KEY")
        self.R2_ACCOUNT_ID = _first_env("R2_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID")
        self.R2_ACCESS_KEY_ID = _first_env("R2_ACCESS_KEY_ID", "CLOUDFLARE_R2_ACCESS_KEY_ID")
        self.R2_SECRET_ACCESS_KEY = _first_env("R2_SECRET_ACCESS_KEY", "CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        self.R2_BUCKET = _first_env("R2_BUCKET", "CLOUDFLARE_R2_BUCKET")
        self.R2_ENDPOINT = _first_env("R2_ENDPOINT")
        self.R2_PUBLIC_BASE_URL = _first_env("R2_PUBLIC_BASE_URL")

        # ── Supabase (database) ────────────────────────────────────────
        self.SUPABASE_URL = _first_env("SUPABASE_URL")
        # 支持多种API Key命名方式（优先级：SUPABASE_API_KEY > SUPABASE_SERVICE_ROLE_KEY > SUPABASE_KEY）
        self.SUPABASE_KEY = _first_env(
            "SUPABASE_API_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_KEY",
        )
        self.SUPABASE_PASSWORD = _first_env("SUPABASE_PASSWORD")
        self.SUPABASE_STORAGE_BUCKET = _first_env("SUPABASE_STORAGE_BUCKET", default="quant-artifacts")
        self.SUPABASE_STORAGE_PUBLIC = _env_bool("SUPABASE_STORAGE_PUBLIC", default=True)
        self.SUPABASE_STORAGE_PATH_PREFIX = _first_env("SUPABASE_STORAGE_PATH_PREFIX", default="quant")

        # ── Email (for notifications) ──────────────────────────────────
        self.SMTP_HOST = _first_env("SMTP_HOST", "SMTP_SERVER", default="smtp.gmail.com")
        self.SMTP_PORT = _env_int("SMTP_PORT", default=587)
        self.SMTP_USER = _first_env("SMTP_USER", "SMTP_USERNAME")
        self.SMTP_PASSWORD = _first_env("SMTP_PASSWORD")
        self.EMAIL_FROM = _first_env(
            "EMAIL_FROM",
            "MAIL_FROM_ADDRESS",
            default="noreply@esg-system.com",
        )

        # ── Scheduler config ───────────────────────────────────────────
        self.SCAN_INTERVAL_MINUTES = _env_int(
            "SCAN_INTERVAL_MINUTES",
            "SCANNER_INTERVAL",
            default=30,
        )
        self.MAX_SCAN_RESULTS = _env_int("MAX_SCAN_RESULTS", default=100)

        # ── API Keys for data sources ──────────────────────────────────
        self.ALPHA_VANTAGE_KEY = _first_env(
            "ALPHA_VANTAGE_KEY",
            "ALPHA_VANTAGE_API_KEY",
        )
        self.NEWS_API_KEY = _first_env("NEWS_API_KEY", "NEWSAPI_KEY")
        self.QUANT_DEFAULT_CAPITAL = float(_first_env("QUANT_DEFAULT_CAPITAL", default="1000000") or 1000000)
        self.QUANT_DEFAULT_BENCHMARK = _first_env("QUANT_DEFAULT_BENCHMARK", default="SPY")
        self.QUANT_DEFAULT_UNIVERSE = _first_env("QUANT_DEFAULT_UNIVERSE", default="ESG_US_LARGE_CAP")
        self.REMOTE_TRAINING_TARGET = _first_env("REMOTE_TRAINING_TARGET", default="Cloud RTX 5090 Finetune Node")
        self.ALPACA_API_KEY = _first_env(
            "ALPACA_API_KEY",
            "ALPACA_KEY_ID",
            "ALPACA_KEY",
            "APCA_API_KEY",
            "APCA_API_KEY_ID",
        )
        self.ALPACA_API_SECRET = _first_env(
            "ALPACA_API_SECRET",
            "ALPACA_SECRET_KEY",
            "ALPACA_SECRET",
            "APCA_API_SECRET",
            "APCA_API_SECRET_KEY",
        )
        self.ALPACA_PAPER_BASE_URL = _first_env(
            "ALPACA_PAPER_BASE_URL",
            "ALPACA_BASE_URL",
            "ALPACA_TRADING_BASE_URL",
            default="https://paper-api.alpaca.markets",
        )
        self.ALPACA_API_TIMEOUT = _env_int("ALPACA_API_TIMEOUT", default=20)
        self.ALPACA_DEFAULT_TEST_NOTIONAL = float(
            _first_env("ALPACA_DEFAULT_TEST_NOTIONAL", default="1.00") or 1.0
        )
        self.ALPACA_MAX_TEST_ORDERS = _env_int("ALPACA_MAX_TEST_ORDERS", default=2)
        self.ALPACA_MAX_ORDER_NOTIONAL = float(
            _first_env("ALPACA_MAX_ORDER_NOTIONAL", default="10.00") or 10.0
        )
        self.ALPACA_ENABLE_LIVE_TRADING = _env_bool("ALPACA_ENABLE_LIVE_TRADING", default=False)

        # ── Debug mode ─────────────────────────────────────────────────
        self.DEBUG = _env_bool("DEBUG", default=True)

   
