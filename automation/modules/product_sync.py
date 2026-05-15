"""Module 1: supplier scraping/local CSV synchronization to WooCommerce."""
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from automation.core.config import AutomationConfig
from automation.core.logging_config import configure_logging

logger = configure_logging()


@dataclass(frozen=True)
class SupplierProduct:
    sku: str
    name: str
    price: Decimal
    stock_quantity: int | None = None
    specifications: str | None = None


def parse_price(raw: str) -> Decimal:
    cleaned = re.sub(r"[^0-9.]", "", raw or "")
    if not cleaned:
        raise ValueError("empty price")
    try:
        price = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"invalid price: {raw}") from exc
    if price <= 0:
        raise ValueError(f"price must be positive: {raw}")
    return price


def load_products_from_csv(path: Path) -> list[SupplierProduct]:
    if not path.exists():
        logger.warning("Supplier CSV not found: %s", path)
        return []
    products: list[SupplierProduct] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for line_no, row in enumerate(reader, start=2):
            try:
                sku = (row.get("sku") or "").strip()
                name = (row.get("name") or "").strip()
                if not sku or not name:
                    raise ValueError("sku and name are required")
                stock = row.get("stock_quantity") or row.get("stock") or ""
                products.append(
                    SupplierProduct(
                        sku=sku,
                        name=name,
                        price=parse_price(row.get("price") or ""),
                        stock_quantity=int(stock) if stock != "" else None,
                        specifications=row.get("specifications"),
                    )
                )
            except Exception as exc:
                logger.error("Skipping invalid CSV row %s: %s", line_no, exc)
    return products


def scrape_supplier_page(url: str) -> list[SupplierProduct]:
    """Scrape static supplier pages with product-card markup.

    Expected selectors are intentionally configurable-by-convention:
    .product-card[data-sku], .product-title, .price, .stock, .specifications
    Use Selenium/Playwright only when supplier pages require JavaScript rendering.
    """
    from bs4 import BeautifulSoup
    from automation.core.http import build_session

    session = build_session()
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    products: list[SupplierProduct] = []
    for card in soup.select(".product-card[data-sku]"):
        try:
            sku = card.get("data-sku", "").strip()
            name = card.select_one(".product-title").get_text(" ", strip=True)
            price = parse_price(card.select_one(".price").get_text(" ", strip=True))
            stock_node = card.select_one(".stock")
            stock = int(re.sub(r"[^0-9]", "", stock_node.get_text())) if stock_node else None
            specs_node = card.select_one(".specifications")
            products.append(SupplierProduct(sku, name, price, stock, specs_node.get_text(" ", strip=True) if specs_node else None))
        except Exception as exc:
            logger.error("Skipping invalid scraped product from %s: %s", url, exc)
    return products


def validate_price_change(current: Decimal | None, incoming: Decimal, config: AutomationConfig) -> bool:
    if current is None or current <= 0:
        return True
    change_ratio = (incoming - current) / current
    if change_ratio <= -config.max_price_drop_pct:
        logger.critical("Blocked suspicious price drop from %s to %s", current, incoming)
        return False
    if change_ratio >= config.max_price_increase_pct:
        logger.critical("Blocked suspicious price increase from %s to %s", current, incoming)
        return False
    return True


def collect_supplier_products(config: AutomationConfig) -> list[SupplierProduct]:
    products = load_products_from_csv(config.supplier_csv_path)
    for url in config.supplier_urls:
        products.extend(scrape_supplier_page(url))
    deduped = {product.sku: product for product in products}
    return list(deduped.values())


def sync_products(products: Iterable[SupplierProduct], config: AutomationConfig) -> int:
    from automation.core.database import ProductRepository
    from automation.core.woocommerce import WooCommerceClient

    repository = ProductRepository(config)
    wc = WooCommerceClient(config)
    updated = 0
    for product in products:
        local = repository.find_by_sku(product.sku)
        if local and not validate_price_change(local.price, product.price, config):
            continue
        wc_product = wc.find_product_by_sku(product.sku)
        if not wc_product:
            logger.warning("SKU not found in WooCommerce: %s", product.sku)
            continue
        wc.update_product(wc_product["id"], product.price, product.stock_quantity)
        updated += 1
        logger.info("Updated SKU %s to price %s and stock %s", product.sku, product.price, product.stock_quantity)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize supplier prices and inventory with WooCommerce.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report products without updating WooCommerce.")
    args = parser.parse_args()
    config = AutomationConfig()
    products = collect_supplier_products(config)
    logger.info("Collected %s supplier products", len(products))
    if args.dry_run:
        for product in products:
            logger.info("DRY RUN: %s | %s | %s", product.sku, product.name, product.price)
        return
    logger.info("Synchronized %s products", sync_products(products, config))


if __name__ == "__main__":
    main()
