"""Module 3: database-grounded customer service chatbot for Telegram/web adapters."""
from __future__ import annotations

import argparse
import re

from automation.core.config import AutomationConfig
from automation.core.database import ProductRepository
from automation.core.http import build_session
from automation.core.logging_config import configure_logging

logger = configure_logging()
SKU_RE = re.compile(r"\b[A-Z0-9][A-Z0-9_-]{2,}\b", re.I)


def faq_answer(message: str, config: AutomationConfig) -> str | None:
    lower = message.lower()
    if any(word in lower for word in ["delivery", "deliver", "ዴሊቨሪ", "ማድረስ"]):
        return "We deliver to: " + ", ".join(config.delivery_locations)
    if any(word in lower for word in ["payment", "pay", "ክፍያ"]):
        return "Payment methods: " + ", ".join(config.payment_methods)
    if any(word in lower for word in ["contact", "phone", "call", "ስልክ"]):
        return "Contact us: " + (" | ".join(config.contact_numbers) or "Please use the website contact form.")
    return None


def query_live_product(message: str, repo: ProductRepository) -> str | None:
    tokens = SKU_RE.findall(message)
    for token in tokens:
        product = repo.find_by_sku(token.upper()) or repo.find_by_sku(token)
        if product:
            return (
                f"{product.title}\nSKU: {product.sku}\n"
                f"Exact current price: {product.price or 'Contact us'}\n"
                f"Availability: {product.stock_quantity if product.stock_quantity is not None else 'Ask support'}"
            )
    results = repo.search_products(message, limit=3)
    if results:
        lines = ["I found these live catalog matches:"]
        for product in results:
            lines.append(f"- {product.title} ({product.sku}): {product.price or 'Contact us'}")
        return "\n".join(lines)
    return None


def llm_rephrase(answer: str, user_message: str, config: AutomationConfig) -> str:
    """Use an LLM only to phrase verified facts; never to invent price data."""
    if not config.llm.api_url:
        return answer
    session = build_session()
    prompt = (
        "You are a concise bilingual English/Amharic store assistant. "
        "Use only the verified facts below. Do not add prices, stock, or promises.\n"
        f"Customer: {user_message}\nVerified facts: {answer}"
    )
    try:
        response = session.post(
            config.llm.api_url,
            json={"model": config.llm.model, "prompt": prompt, "stream": False},
            headers={"Authorization": f"Bearer {config.llm.api_key}"} if config.llm.api_key else None,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response") or data.get("choices", [{}])[0].get("message", {}).get("content") or answer
    except Exception as exc:
        logger.warning("LLM unavailable; returning verified raw answer: %s", exc)
        return answer


def alert_human(user_message: str, config: AutomationConfig) -> None:
    if not (config.telegram.bot_token and config.telegram.admin_chat_id):
        logger.warning("Human handoff requested but Telegram admin settings are not configured")
        return
    session = build_session()
    response = session.post(
        f"https://api.telegram.org/bot{config.telegram.bot_token}/sendMessage",
        json={"chat_id": config.telegram.admin_chat_id, "text": f"Human handoff needed:\n{user_message}"},
        timeout=30,
    )
    response.raise_for_status()


def answer_customer(user_message: str, config: AutomationConfig) -> str:
    repo = ProductRepository(config)
    verified = faq_answer(user_message, config) or query_live_product(user_message, repo)
    if verified:
        return llm_rephrase(verified, user_message, config)
    if any(word in user_message.lower() for word in ["bulk", "discount", "negotiate", "custom", "wholesale"]):
        alert_human(user_message, config)
        return "Thanks. I alerted a human admin to help with your custom/bulk request."
    return "I could not verify that from the live catalog. Please send a product SKU/name or contact support."


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the support chatbot one message from the command line.")
    parser.add_argument("message")
    args = parser.parse_args()
    print(answer_customer(args.message, AutomationConfig()))


if __name__ == "__main__":
    main()
