"""Module 2: marketing copy, media generation, and social publishing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from automation.core.config import AutomationConfig, require_env
from automation.core.database import ProductRecord, ProductRepository
from automation.core.http import build_session
from automation.core.logging_config import configure_logging

logger = configure_logging()
STATE_FILE = Path("data/marketing_state.json")


def format_marketing_copy(product: ProductRecord, config: AutomationConfig) -> str:
    contacts = " | ".join(config.contact_numbers) or "See website"
    product_url = f"{config.website_url}/?p={product.product_id}" if config.website_url else "Website link available soon"
    availability = "In stock" if (product.stock_quantity or 0) > 0 else "Contact us for availability"
    return (
        f"🔥 New deal: {product.title}\n\n"
        f"SKU: {product.sku}\n"
        f"Price: {product.price or 'Contact us'}\n"
        f"Availability: {availability}\n"
        f"Contact: {contacts}\n"
        f"Order: {product_url}\n\n"
        "| Detail | Value |\n|---|---|\n"
        f"| SKU | {product.sku} |\n"
        f"| Price | {product.price or 'TBD'} |\n"
        f"| Stock | {product.stock_quantity if product.stock_quantity is not None else 'Ask'} |"
    )


def generate_product_image(product: ProductRecord, config: AutomationConfig) -> Path:
    config.media_dir.mkdir(parents=True, exist_ok=True)
    template = Path("automation/templates/promo_background.png")
    if template.exists():
        image = Image.open(template).convert("RGB").resize((1080, 1080))
    else:
        image = Image.new("RGB", (1080, 1080), (20, 42, 75))
    draw = ImageDraw.Draw(image)
    font_big = ImageFont.load_default(size=56)
    font_med = ImageFont.load_default(size=38)
    font_small = ImageFont.load_default(size=28)
    draw.rounded_rectangle((70, 670, 1010, 980), radius=36, fill=(255, 255, 255))
    draw.text((95, 700), product.title[:55], fill=(15, 30, 55), font=font_big)
    draw.text((95, 790), f"Price: {product.price or 'Contact us'}", fill=(220, 70, 45), font=font_med)
    draw.text((95, 850), f"SKU: {product.sku}", fill=(55, 55, 55), font=font_small)
    draw.text((95, 900), "Contact: " + (" | ".join(config.contact_numbers) or "Website"), fill=(55, 55, 55), font=font_small)
    output = config.media_dir / f"promo_{product.product_id}.jpg"
    image.save(output, quality=90, optimize=True)
    logger.info("Generated marketing image: %s", output)
    return output


def post_to_telegram(text: str, image_path: Path | None, config: AutomationConfig) -> None:
    require_env(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"])
    session = build_session()
    base = f"https://api.telegram.org/bot{config.telegram.bot_token}"
    if image_path:
        with image_path.open("rb") as image_file:
            response = session.post(
                f"{base}/sendPhoto",
                data={"chat_id": config.telegram.channel_id, "caption": text[:1024], "parse_mode": "Markdown"},
                files={"photo": image_file},
                timeout=60,
            )
    else:
        response = session.post(f"{base}/sendMessage", json={"chat_id": config.telegram.channel_id, "text": text}, timeout=30)
    response.raise_for_status()
    logger.info("Posted product promotion to Telegram")


def post_to_facebook(text: str, image_path: Path | None, config: AutomationConfig) -> None:
    if not (config.meta.page_id and config.meta.access_token):
        logger.warning("Meta credentials are not configured; skipping Facebook post")
        return
    session = build_session()
    if image_path:
        with image_path.open("rb") as image_file:
            response = session.post(
                f"https://graph.facebook.com/v20.0/{config.meta.page_id}/photos",
                data={"caption": text, "access_token": config.meta.access_token},
                files={"source": image_file},
                timeout=60,
            )
    else:
        response = session.post(
            f"https://graph.facebook.com/v20.0/{config.meta.page_id}/feed",
            data={"message": text, "access_token": config.meta.access_token},
            timeout=30,
        )
    response.raise_for_status()
    logger.info("Posted product promotion to Facebook")


def load_seen() -> set[int]:
    if not STATE_FILE.exists():
        return set()
    return set(json.loads(STATE_FILE.read_text()).get("seen_product_ids", []))


def save_seen(seen: set[int]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"seen_product_ids": sorted(seen)}, indent=2))


def publish_recent_events(config: AutomationConfig, minutes: int) -> int:
    repo = ProductRepository(config)
    seen = load_seen()
    posted = 0
    processed_ids: list[int] = []
    try:
        products = repo.unprocessed_event_products()
    except Exception as exc:
        logger.warning("Event trigger table unavailable; falling back to recent modified products: %s", exc)
        products = repo.recent_product_events(minutes)
    for product in products:
        if product.product_id in seen:
            continue
        text = format_marketing_copy(product, config)
        image = generate_product_image(product, config)
        post_to_telegram(text, image, config)
        post_to_facebook(text, image, config)
        seen.add(product.product_id)
        processed_ids.append(product.product_id)
        posted += 1
    save_seen(seen)
    if processed_ids:
        try:
            repo.mark_events_processed(processed_ids)
        except Exception as exc:
            logger.warning("Could not mark marketing events processed: %s", exc)
    return posted


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish social media posts for recent product changes.")
    parser.add_argument("--minutes", type=int, default=15)
    args = parser.parse_args()
    config = AutomationConfig()
    logger.info("Published %s marketing events", publish_recent_events(config, args.minutes))


if __name__ == "__main__":
    main()
