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


def _env_float(*names: str, default: float) -> float:
    value = _first_env(*names, default=str(default))
    try:
        return float(value)
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

        self.OPENAI_API_KEY = _first_env("OPENAI_API_KEY")
        self.ANTHROPIC_API_KEY = _first_env("ANTHROPIC_API_KEY")
        self.DEEPSEEK_API_KEY = _first_env("DEEPSEEK_API_KEY")
        self.REMOTE_LLM_URL = _first_env("REMOTE_LLM_URL")
        self.REMOTE_LLM_API_KEY = _first_env("REMOTE_LLM_API_KEY")
        self.QDRANT_URL = _first_env("QDRANT_URL", default="http://localhost:6333")
        self.REMOTE_LLM_TIMEOUT = _env_int("REMOTE_LLM_TIMEOUT", default=180)
        self.REMOTE_LLM_CONNECT_TIMEOUT = _env_float("REMOTE_LLM_CONNECT_TIMEOUT", default=2.0)
        self.REMOTE_LLM_HEALTH_TIMEOUT = _env_float("REMOTE_LLM_HEALTH_TIMEOUT", default=2.0)
        self.REMOTE_LLM_COOLDOWN_SECONDS = _env_int("REMOTE_LLM_COOLDOWN_SECONDS", default=60)
        self.REMOTE_LLM_HEALTH_TTL_SECONDS = _env_int("REMOTE_LLM_HEALTH_TTL_SECONDS", default=30)
        self.LLM_RESPONSE_CACHE_TTL_SECONDS = _env_int("LLM_RESPONSE_CACHE_TTL_SECONDS", default=900)
        self.CLOUD_LLM_TIMEOUT_SECONDS = _env_float("CLOUD_LLM_TIMEOUT_SECONDS", default=20.0)
        self.CLOUD_LLM_MAX_RETRIES = _env_int("CLOUD_LLM_MAX_RETRIES", default=1)
        self.ESG_DATA_HTTP_TIMEOUT_SECONDS = _env_float("ESG_DATA_HTTP_TIMEOUT_SECONDS", default=4.0)
        self.ESG_NEWS_HTTP_TIMEOUT_SECONDS = _env_float("ESG_NEWS_HTTP_TIMEOUT_SECONDS", default=4.0)
        self.ESG_REPORT_CACHE_TTL_SECONDS = _env_int("ESG_REPORT_CACHE_TTL_SECONDS", default=900)

        self.AWS_ACCESS_KEY_ID = _first_env("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = _first_env("AWS_SECRET_ACCESS_KEY")
        self.R2_ACCOUNT_ID = _first_env("R2_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID")
        self.R2_ACCESS_KEY_ID = _first_env("R2_ACCESS_KEY_ID", "CLOUDFLARE_R2_ACCESS_KEY_ID")
        self.R2_SECRET_ACCESS_KEY = _first_env("R2_SECRET_ACCESS_KEY", "CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        self.R2_BUCKET = _first_env("R2_BUCKET", "CLOUDFLARE_R2_BUCKET")
        self.R2_ENDPOINT = _first_env("R2_ENDPOINT")
        self.R2_PUBLIC_BASE_URL = _first_env("R2_PUBLIC_BASE_URL")

        self.SUPABASE_URL = _first_env("SUPABASE_URL")
        self.SUPABASE_KEY = _first_env(
            "SUPABASE_API_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_KEY",
        )
        self.SUPABASE_PASSWORD = _first_env("SUPABASE_PASSWORD")
        self.SUPABASE_STORAGE_BUCKET = _first_env("SUPABASE_STORAGE_BUCKET", default="quant-artifacts")
        self.SUPABASE_STORAGE_PUBLIC = _env_bool("SUPABASE_STORAGE_PUBLIC", default=True)
        self.SUPABASE_STORAGE_PATH_PREFIX = _first_env("SUPABASE_STORAGE_PATH_PREFIX", default="quant")

        self.SMTP_HOST = _first_env("SMTP_HOST", "SMTP_SERVER", default="smtp.gmail.com")
        self.SMTP_PORT = _env_int("SMTP_PORT", default=587)
        self.SMTP_USER = _first_env("SMTP_USER", "SMTP_USERNAME")
        self.SMTP_PASSWORD = _first_env("SMTP_PASSWORD")
        self.EMAIL_FROM = _first_env(
            "EMAIL_FROM",
            "MAIL_FROM_ADDRESS",
            default="noreply@esg-system.com",
        )

        self.SCAN_INTERVAL_MINUTES = _env_int(
            "SCAN_INTERVAL_MINUTES",
            "SCANNER_INTERVAL",
            default=30,
        )
        self.MAX_SCAN_RESULTS = _env_int("MAX_SCAN_RESULTS", default=100)

        self.ALPHA_VANTAGE_KEY = _first_env(
            "ALPHA_VANTAGE_KEY",
            "ALPHA_VANTAGE_API_KEY",
        )
        self.NEWS_API_KEY = _first_env("NEWS_API_KEY", "NEWSAPI_KEY")
        self.QUANT_DEFAULT_CAPITAL = _env_float("QUANT_DEFAULT_CAPITAL", default=1_000_000.0)
        self.QUANT_DEFAULT_BENCHMARK = _first_env("QUANT_DEFAULT_BENCHMARK", default="SPY")
        self.QUANT_DEFAULT_UNIVERSE = _first_env("QUANT_DEFAULT_UNIVERSE", default="ESG_US_LARGE_CAP")
        self.REMOTE_TRAINING_TARGET = _first_env("REMOTE_TRAINING_TARGET", default="Cloud RTX 5090 Finetune Node")
        self.MARKET_DATA_PROVIDER = _first_env("MARKET_DATA_PROVIDER", default="alpaca,yfinance")
        self.MARKET_DATA_CACHE_DB = _first_env("MARKET_DATA_CACHE_DB", default="storage/quant/market_data/bars.sqlite3")
        self.MARKET_DATA_CACHE_MAX_AGE_HOURS = _env_int("MARKET_DATA_CACHE_MAX_AGE_HOURS", default=24)
        self.MARKET_DATA_ALPACA_FEED = _first_env("MARKET_DATA_ALPACA_FEED", default="iex")
        self.MARKET_DATA_HISTORY_DAYS = _env_int("MARKET_DATA_HISTORY_DAYS", default=240)
        self.MOMENTUM_SHORT_WINDOW = _env_int("MOMENTUM_SHORT_WINDOW", default=20)
        self.MOMENTUM_LONG_WINDOW = _env_int("MOMENTUM_LONG_WINDOW", default=60)
        self.SIGNAL_ENGINE_DEFAULT = _first_env("SIGNAL_ENGINE_DEFAULT", default="hybrid_momentum")
        self.SCHEDULER_TIMEZONE = _first_env("SCHEDULER_TIMEZONE", default="America/New_York")
        self.SCHEDULER_SIGNAL_UNIVERSE = _first_env("SCHEDULER_SIGNAL_UNIVERSE", default="AAPL,MSFT,TSLA")
        self.SCHEDULER_PREOPEN_SIGNAL_TIME = _first_env("SCHEDULER_PREOPEN_SIGNAL_TIME", default="09:00")
        self.SCHEDULER_EXECUTION_TIME = _first_env("SCHEDULER_EXECUTION_TIME", default="09:31")
        self.SCHEDULER_AUTO_SUBMIT = _env_bool("SCHEDULER_AUTO_SUBMIT", default=False)
        self.SCHEDULER_MAX_EXECUTION_SYMBOLS = _env_int("SCHEDULER_MAX_EXECUTION_SYMBOLS", default=2)
        self.SCHEDULER_MAX_DAILY_NOTIONAL_USD = _env_float("SCHEDULER_MAX_DAILY_NOTIONAL_USD", default=1000.0)
        self.SCHEDULER_ENABLE_AUTO_CANCEL = _env_bool("SCHEDULER_ENABLE_AUTO_CANCEL", default=True)
        self.SCHEDULER_CANCEL_STALE_AFTER_MINUTES = _env_int("SCHEDULER_CANCEL_STALE_AFTER_MINUTES", default=20)
        self.SCHEDULER_ENABLE_AUTO_RETRY = _env_bool("SCHEDULER_ENABLE_AUTO_RETRY", default=True)
        self.SCHEDULER_MAX_RETRY_ATTEMPTS = _env_int("SCHEDULER_MAX_RETRY_ATTEMPTS", default=1)
        self.SCHEDULER_RETRY_DELAY_MINUTES = _env_int("SCHEDULER_RETRY_DELAY_MINUTES", default=2)
        self.SCHEDULER_SYNC_INTERVAL_MINUTES = _env_int("SCHEDULER_SYNC_INTERVAL_MINUTES", default=5)
        self.SCHEDULER_SYNC_END_TIME = _first_env("SCHEDULER_SYNC_END_TIME", default="16:10")
        self.SCHEDULER_FALLBACK_TO_DEFAULT_UNIVERSE = _env_bool("SCHEDULER_FALLBACK_TO_DEFAULT_UNIVERSE", default=True)
        self.SCHEDULER_STATE_PATH = _first_env("SCHEDULER_STATE_PATH", default="storage/quant/scheduler/runtime_state.json")
        self.SCHEDULER_HEARTBEAT_PATH = _first_env("SCHEDULER_HEARTBEAT_PATH", default="storage/quant/scheduler/heartbeat.json")
        self.SCHEDULER_LOCK_PATH = _first_env("SCHEDULER_LOCK_PATH", default="storage/quant/scheduler/worker.lock")
        self.SCHEDULER_LOCK_STALE_MINUTES = _env_int("SCHEDULER_LOCK_STALE_MINUTES", default=240)

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
        self.ALPACA_DEFAULT_TEST_NOTIONAL = _env_float("ALPACA_DEFAULT_TEST_NOTIONAL", default=1.0)
        self.ALPACA_MAX_TEST_ORDERS = _env_int("ALPACA_MAX_TEST_ORDERS", default=2)
        self.ALPACA_MAX_ORDER_NOTIONAL = _env_float("ALPACA_MAX_ORDER_NOTIONAL", default=10.0)
        self.ALPACA_ENABLE_LIVE_TRADING = _env_bool("ALPACA_ENABLE_LIVE_TRADING", default=False)

        self.QUANT_BROKER_DEFAULT = _env_choice(
            "QUANT_BROKER_DEFAULT",
            default="alpaca",
            allowed={"alpaca", "ibkr", "tiger", "longbridge"},
        )
        self.EXECUTION_REQUIRE_MARKET_OPEN = _env_bool("EXECUTION_REQUIRE_MARKET_OPEN", default=False)
        self.EXECUTION_MAX_DAILY_ORDERS = _env_int("EXECUTION_MAX_DAILY_ORDERS", default=25)
        self.EXECUTION_MAX_NOTIONAL_PER_ORDER = _env_float("EXECUTION_MAX_NOTIONAL_PER_ORDER", default=2500.0)
        self.EXECUTION_MIN_BUYING_POWER_BUFFER = _env_float("EXECUTION_MIN_BUYING_POWER_BUFFER", default=100.0)
        self.EXECUTION_SINGLE_NAME_WEIGHT_CAP = _env_float("EXECUTION_SINGLE_NAME_WEIGHT_CAP", default=0.26)
        self.EXECUTION_DEFAULT_SLIPPAGE_BPS = _env_float("EXECUTION_DEFAULT_SLIPPAGE_BPS", default=8.0)
        self.EXECUTION_DEFAULT_IMPACT_BPS = _env_float("EXECUTION_DEFAULT_IMPACT_BPS", default=5.0)
        self.EXECUTION_SLIPPAGE_VOL_MULTIPLIER = _env_float("EXECUTION_SLIPPAGE_VOL_MULTIPLIER", default=42.0)
        self.EXECUTION_IMPACT_VOL_MULTIPLIER = _env_float("EXECUTION_IMPACT_VOL_MULTIPLIER", default=28.0)
        self.EXECUTION_IMPACT_PARTICIPATION_COEFF = _env_float("EXECUTION_IMPACT_PARTICIPATION_COEFF", default=160.0)
        self.EXECUTION_FILL_PROBABILITY_BASE = _env_float("EXECUTION_FILL_PROBABILITY_BASE", default=0.72)
        self.EXECUTION_FILL_PROBABILITY_MIN = _env_float("EXECUTION_FILL_PROBABILITY_MIN", default=0.08)
        self.EXECUTION_FILL_PROBABILITY_MAX = _env_float("EXECUTION_FILL_PROBABILITY_MAX", default=0.98)
        self.EXECUTION_CANARY_RELEASE_PERCENT = _env_float("EXECUTION_CANARY_RELEASE_PERCENT", default=0.15)
        self.EXECUTION_CANARY_ENABLED = _env_bool("EXECUTION_CANARY_ENABLED", default=True)
        self.EXECUTION_KILL_SWITCH = _env_bool("EXECUTION_KILL_SWITCH", default=False)
        self.EXECUTION_KILL_SWITCH_REASON = _first_env(
            "EXECUTION_KILL_SWITCH_REASON",
            default="Manual operator override. Routing remains disabled until released.",
        )
        self.EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES = _env_int(
            "EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES",
            default=90,
        )
        self.EXECUTION_REALTIME_REFRESH_SECONDS = _env_int(
            "EXECUTION_REALTIME_REFRESH_SECONDS",
            default=5,
        )
        self.EXECUTION_STALE_ORDER_MINUTES = _env_int("EXECUTION_STALE_ORDER_MINUTES", default=20)
        self.EXECUTION_STALE_ORDER_ALERT_THRESHOLD = _env_int(
            "EXECUTION_STALE_ORDER_ALERT_THRESHOLD",
            default=1,
        )
        self.EXECUTION_WS_ENABLED = _env_bool("EXECUTION_WS_ENABLED", default=True)

        self.ALPHA_RANKER_BACKEND = _first_env("ALPHA_RANKER_BACKEND", default="auto")
        self.ALPHA_RANKER_CHECKPOINT_DIR = _first_env(
            "ALPHA_RANKER_CHECKPOINT_DIR",
            default="model-serving/checkpoint/alpha_ranker",
        )
        self.ALPHA_RANKER_DATA_DIR = _first_env("ALPHA_RANKER_DATA_DIR", default="data/alpha_ranker")
        self.ALPHA_RANKER_ENABLED = _env_bool("ALPHA_RANKER_ENABLED", default=True)
        self.P1_MODEL_SUITE_ENABLED = _env_bool("P1_MODEL_SUITE_ENABLED", default=True)
        self.P1_MODEL_SUITE_CHECKPOINT_DIR = _first_env(
            "P1_MODEL_SUITE_CHECKPOINT_DIR",
            default="model-serving/checkpoint/p1_suite",
        )
        self.P1_MODEL_SUITE_DATA_DIR = _first_env("P1_MODEL_SUITE_DATA_DIR", default="data/p1_stack")
        self.P1_SEQUENCE_ENABLED = _env_bool("P1_SEQUENCE_ENABLED", default=True)
        self.P1_SEQUENCE_CHECKPOINT_DIR = _first_env(
            "P1_SEQUENCE_CHECKPOINT_DIR",
            default="model-serving/checkpoint/sequence_forecaster",
        )
        self.P1_SEQUENCE_TARGETS = _first_env(
            "P1_SEQUENCE_TARGETS",
            default="forward_return_1d,forward_return_5d,future_volatility_10d,future_max_drawdown_20d",
        )
        self.P1_SEQUENCE_BLEND_WEIGHT = _env_float("P1_SEQUENCE_BLEND_WEIGHT", default=0.35)
        self.P1_CALIBRATION_ENABLED = _env_bool("P1_CALIBRATION_ENABLED", default=True)
        self.P1_CALIBRATION_TEMPERATURE = _env_float("P1_CALIBRATION_TEMPERATURE", default=0.82)
        self.P1_CONFIDENCE_SLOPE = _env_float("P1_CONFIDENCE_SLOPE", default=0.9)
        self.P1_STACK_WEIGHT_ALPHA = _env_float("P1_STACK_WEIGHT_ALPHA", default=0.18)
        self.P1_STACK_WEIGHT_RETURN_1D = _env_float("P1_STACK_WEIGHT_RETURN_1D", default=0.14)
        self.P1_STACK_WEIGHT_RETURN_5D = _env_float("P1_STACK_WEIGHT_RETURN_5D", default=0.28)
        self.P1_STACK_WEIGHT_RISK = _env_float("P1_STACK_WEIGHT_RISK", default=0.22)
        self.P1_STACK_WEIGHT_REGIME = _env_float("P1_STACK_WEIGHT_REGIME", default=0.18)
        self.EVENT_CLASSIFIER_ENABLED = _env_bool("EVENT_CLASSIFIER_ENABLED", default=True)
        self.EVENT_CLASSIFIER_CHECKPOINT_ROOT = _first_env(
            "EVENT_CLASSIFIER_CHECKPOINT_ROOT",
            default="model-serving/checkpoint/event_classifier",
        )
        self.EVENT_CLASSIFIER_TARGET = _first_env("EVENT_CLASSIFIER_TARGET", default="controversy_label")
        self.EVENT_CLASSIFIER_TASKS = _first_env(
            "EVENT_CLASSIFIER_TASKS",
            default="controversy_label,severity,impact_area,event_type",
        )
        self.EVENT_CLASSIFIER_MAX_LENGTH = _env_int("EVENT_CLASSIFIER_MAX_LENGTH", default=256)
        self.P2_DECISION_STACK_ENABLED = _env_bool("P2_DECISION_STACK_ENABLED", default=True)
        self.P2_SELECTOR_CHECKPOINT_DIR = _first_env(
            "P2_SELECTOR_CHECKPOINT_DIR",
            default="model-serving/checkpoint/p2_selector",
        )
        self.P2_SELECTOR_DATA_DIR = _first_env("P2_SELECTOR_DATA_DIR", default="data/p2_stack")
        self.P2_BANDIT_ENABLED = _env_bool("P2_BANDIT_ENABLED", default=True)
        self.P2_BANDIT_CHECKPOINT_DIR = _first_env(
            "P2_BANDIT_CHECKPOINT_DIR",
            default="model-serving/checkpoint/contextual_bandit",
        )
        self.P2_BANDIT_BLEND_WEIGHT = _env_float("P2_BANDIT_BLEND_WEIGHT", default=0.4)
        self.P2_BANDIT_SIZE_MULTIPLIER_MIN = _env_float("P2_BANDIT_SIZE_MULTIPLIER_MIN", default=0.55)
        self.P2_BANDIT_SIZE_MULTIPLIER_MAX = _env_float("P2_BANDIT_SIZE_MULTIPLIER_MAX", default=1.35)
        self.P2_BANDIT_EXECUTION_DELAY_MAX_SECONDS = _env_int("P2_BANDIT_EXECUTION_DELAY_MAX_SECONDS", default=900)
        self.P2_GRAPH_EDGE_THRESHOLD = _env_float("P2_GRAPH_EDGE_THRESHOLD", default=0.58)
        self.P2_DECISION_MIN_SCORE = _env_float("P2_DECISION_MIN_SCORE", default=0.54)
        self.P2_GRAPH_CONTAGION_LIMIT = _env_float("P2_GRAPH_CONTAGION_LIMIT", default=0.62)
        self.P2_GRAPH_CHECKPOINT_DIR = _first_env(
            "P2_GRAPH_CHECKPOINT_DIR",
            default="model-serving/checkpoint/gnn_graph",
        )
        self.P2_GRAPH_ENGINE = _first_env("P2_GRAPH_ENGINE", default="auto")
        self.P2_REGIME_MIXTURE_ENABLED = _env_bool("P2_REGIME_MIXTURE_ENABLED", default=True)
        self.P2_CALIBRATION_ENABLED = _env_bool("P2_CALIBRATION_ENABLED", default=True)
        self.P2_DECISION_CONFIDENCE_TEMPERATURE = _env_float("P2_DECISION_CONFIDENCE_TEMPERATURE", default=0.88)

        self.IBKR_GATEWAY_URL = _first_env("IBKR_GATEWAY_URL")
        self.IBKR_ACCOUNT_ID = _first_env("IBKR_ACCOUNT_ID")
        self.IBKR_USERNAME = _first_env("IBKR_USERNAME")
        self.IBKR_PASSWORD = _first_env("IBKR_PASSWORD")
        self.IBKR_PAPER_MODE = _env_bool("IBKR_PAPER_MODE", default=True)
        self.IBKR_VALIDATE_SSL = _env_bool("IBKR_VALIDATE_SSL", default=False)

        self.TIGER_ID = _first_env("TIGER_ID", "TIGER_APP_ID")
        self.TIGER_ACCOUNT = _first_env("TIGER_ACCOUNT", "TIGER_ACCOUNT_ID")
        self.TIGER_PRIVATE_KEY_PATH = _first_env("TIGER_PRIVATE_KEY_PATH")
        self.TIGER_ACCESS_TOKEN = _first_env("TIGER_ACCESS_TOKEN")
        self.TIGER_REGION = _first_env("TIGER_REGION", default="US")
        self.TIGER_PAPER_MODE = _env_bool("TIGER_PAPER_MODE", default=True)

        self.LONGBRIDGE_APP_KEY = _first_env("LONGBRIDGE_APP_KEY")
        self.LONGBRIDGE_APP_SECRET = _first_env("LONGBRIDGE_APP_SECRET")
        self.LONGBRIDGE_ACCESS_TOKEN = _first_env("LONGBRIDGE_ACCESS_TOKEN")
        self.LONGBRIDGE_REGION = _first_env("LONGBRIDGE_REGION", default="us")
        self.LONGBRIDGE_PAPER_MODE = _env_bool("LONGBRIDGE_PAPER_MODE", default=True)

        self.EXECUTION_API_KEY = _first_env("EXECUTION_API_KEY")
        self.ADMIN_API_KEY = _first_env("ADMIN_API_KEY")
        self.OPS_API_KEY = _first_env("OPS_API_KEY")
        self.AUTH_DEFAULT_REQUIRED = _env_bool("AUTH_DEFAULT_REQUIRED", default=True)
        self.AUTH_ALLOW_LOCALHOST_DEV = _env_bool("AUTH_ALLOW_LOCALHOST_DEV", default=True)
        self.AUTH_BEARER_ONLY = _env_bool("AUTH_BEARER_ONLY", default=False)
        self.AUDIT_LOG_ENABLED = _env_bool("AUDIT_LOG_ENABLED", default=True)
        self.AUDIT_LOG_RETENTION_DAYS = _env_int("AUDIT_LOG_RETENTION_DAYS", default=30)
        self.METRICS_PUBLIC = _env_bool("METRICS_PUBLIC", default=False)
        self.MODEL_REGISTRY_PATH = _first_env("MODEL_REGISTRY_PATH", default="storage/quant/model_registry/current_runtime.json")
        self.MODEL_RELEASE_LOG_PATH = _first_env("MODEL_RELEASE_LOG_PATH", default="storage/quant/model_registry/release_log.jsonl")
        self.PAPER_FEEDBACK_DIR = _first_env("PAPER_FEEDBACK_DIR", default="storage/quant/paper_feedback")
        self.PAPER_FEEDBACK_CAPTURE_ENABLED = _env_bool("PAPER_FEEDBACK_CAPTURE_ENABLED", default=True)
        self.API_HEALTHCHECK_REQUIRED_COMPONENTS = _first_env(
            "API_HEALTHCHECK_REQUIRED_COMPONENTS",
            default="api,quant_scheduler,remote_llm,qdrant",
        )
        self.AUTO_RECOVERY_ENABLED = _env_bool("AUTO_RECOVERY_ENABLED", default=True)

        self.DEBUG = _env_bool("DEBUG", default=True)
