"""Module 4c: uptime and product-table integrity monitoring with Telegram alerts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from automation.core.config import AutomationConfig
from automation.core.database import ProductRepository
from automation.core.http import build_session
from automation.core.logging_config import configure_logging

logger = configure_logging()
STATE_FILE = Path("data/monitor_state.json")


def send_alert(message: str, config: AutomationConfig) -> None:
    if not (config.telegram.bot_token and config.telegram.admin_chat_id):
        logger.error("ALERT (Telegram not configured): %s", message)
        return
    session = build_session()
    response = session.post(
        f"https://api.telegram.org/bot{config.telegram.bot_token}/sendMessage",
        json={"chat_id": config.telegram.admin_chat_id, "text": message},
        timeout=20,
    )
    response.raise_for_status()
    logger.info("Telegram alert sent")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_uptime(config: AutomationConfig) -> int:
    session = build_session()
    failures = 0
    for url in config.monitor_urls or ([config.website_url] if config.website_url else []):
        try:
            response = session.get(url, timeout=20)
            if response.status_code >= 400:
                failures += 1
                send_alert(f"Website health check failed: {url} status={response.status_code}", config)
        except Exception as exc:
            failures += 1
            send_alert(f"Website is unreachable: {url}\n{exc}", config)
    return failures


def check_database_integrity(config: AutomationConfig) -> bool:
    repo = ProductRepository(config)
    state = load_state()
    checksum = repo.product_audit_checksum()
    previous = state.get("product_checksum")
    state["product_checksum"] = checksum
    save_state(state)
    if previous and previous != checksum:
        send_alert("Product price/stock checksum changed. Verify this was caused by an approved automation/user action.", config)
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run uptime and product integrity checks.")
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()
    config = AutomationConfig()
    failures = check_uptime(config)
    if not args.skip_db:
        check_database_integrity(config)
    logger.info("Monitoring complete with %s uptime failures", failures)


if __name__ == "__main__":
    main()
