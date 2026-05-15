"""Environment-driven configuration for all automation modules."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[2]


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding existing environment values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT_DIR / ".env")


def _csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


def require_env(names: Iterable[str]) -> None:
    """Fail fast when a required setting is missing."""
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "127.0.0.1")
    port: int = _int("DB_PORT", 3306)
    name: str = os.getenv("DB_NAME", "wordpress")
    user: str = os.getenv("DB_USER", "wordpress")
    password: str = os.getenv("DB_PASSWORD", "")
    table_prefix: str = os.getenv("WP_TABLE_PREFIX", "wp_")

    @property
    def sqlalchemy_url(self) -> str:
        return f"mysql+mysqlconnector://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass(frozen=True)
class WooCommerceConfig:
    base_url: str = os.getenv("WC_BASE_URL", "").rstrip("/")
    consumer_key: str = os.getenv("WC_CONSUMER_KEY", "")
    consumer_secret: str = os.getenv("WC_CONSUMER_SECRET", "")
    timeout_seconds: int = _int("HTTP_TIMEOUT_SECONDS", 30)


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    admin_chat_id: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")


@dataclass(frozen=True)
class MetaConfig:
    page_id: str = os.getenv("META_PAGE_ID", "")
    access_token: str = os.getenv("META_ACCESS_TOKEN", "")


@dataclass(frozen=True)
class LLMConfig:
    provider: str = os.getenv("LLM_PROVIDER", "ollama")
    api_url: str = os.getenv("LLM_API_URL", "http://127.0.0.1:11434/api/generate")
    model: str = os.getenv("LLM_MODEL", "gemma3:4b")
    api_key: str = os.getenv("LLM_API_KEY", "")


@dataclass(frozen=True)
class AutomationConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    woocommerce: WooCommerceConfig = field(default_factory=WooCommerceConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    meta: MetaConfig = field(default_factory=MetaConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    log_file: Path = Path(os.getenv("AUTOMATION_LOG_FILE", ROOT_DIR / "automation.log"))
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
    backup_dir: Path = Path(os.getenv("BACKUP_DIR", ROOT_DIR / "backups"))
    media_dir: Path = Path(os.getenv("MEDIA_DIR", ROOT_DIR / "media"))
    website_url: str = os.getenv("WEBSITE_URL", "").rstrip("/")
    contact_numbers: list[str] = field(default_factory=lambda: _csv("CONTACT_NUMBERS"))
    delivery_locations: list[str] = field(default_factory=lambda: _csv("DELIVERY_LOCATIONS", "Addis Ababa"))
    payment_methods: list[str] = field(default_factory=lambda: _csv("PAYMENT_METHODS", "Cash,Bank Transfer,Mobile Money"))
    max_price_drop_pct: float = _float("MAX_PRICE_DROP_PCT", 0.90)
    max_price_increase_pct: float = _float("MAX_PRICE_INCREASE_PCT", 2.00)
    monitor_urls: list[str] = field(default_factory=lambda: _csv("MONITOR_URLS"))
    remote_backup_target: str = os.getenv("REMOTE_BACKUP_TARGET", "")
    supplier_csv_path: Path = Path(os.getenv("SUPPLIER_CSV_PATH", ROOT_DIR / "data" / "supplier_products.csv"))
    supplier_urls: list[str] = field(default_factory=lambda: _csv("SUPPLIER_URLS"))
