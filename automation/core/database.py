"""Database access helpers for WordPress/WooCommerce product data."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

from automation.core.config import AutomationConfig


@dataclass(frozen=True)
class ProductRecord:
    product_id: int
    sku: str
    title: str
    price: Decimal | None
    regular_price: Decimal | None
    stock_quantity: int | None
    permalink: str | None = None
    image_url: str | None = None
    specs: dict[str, str] | None = None


class ProductRepository:
    """Read-only product queries plus an audit snapshot for monitoring."""

    def __init__(self, config: AutomationConfig):
        self.config = config
        self.engine: Engine = create_engine(config.db.sqlalchemy_url, pool_pre_ping=True, pool_recycle=3600)
        self.prefix = config.db.table_prefix

    @contextmanager
    def connection(self) -> Iterator:
        with self.engine.begin() as conn:
            yield conn

    def find_by_sku(self, sku: str) -> ProductRecord | None:
        sql = text(
            f"""
            SELECT p.ID AS product_id, sku.meta_value AS sku, p.post_title AS title,
                   price.meta_value AS price, regular.meta_value AS regular_price,
                   stock.meta_value AS stock_quantity,
                   guid.guid AS image_url
            FROM {self.prefix}posts p
            JOIN {self.prefix}postmeta sku ON sku.post_id = p.ID AND sku.meta_key = '_sku'
            LEFT JOIN {self.prefix}postmeta price ON price.post_id = p.ID AND price.meta_key = '_price'
            LEFT JOIN {self.prefix}postmeta regular ON regular.post_id = p.ID AND regular.meta_key = '_regular_price'
            LEFT JOIN {self.prefix}postmeta thumb ON thumb.post_id = p.ID AND thumb.meta_key = '_thumbnail_id'
            LEFT JOIN {self.prefix}posts guid ON guid.ID = thumb.meta_value
            LEFT JOIN {self.prefix}postmeta stock ON stock.post_id = p.ID AND stock.meta_key = '_stock'
            WHERE sku.meta_value = :sku AND p.post_type IN ('product','product_variation')
            LIMIT 1
            """
        )
        with self.connection() as conn:
            row = conn.execute(sql, {"sku": sku}).mappings().first()
        if not row:
            return None
        return ProductRecord(
            product_id=int(row["product_id"]),
            sku=row["sku"],
            title=row["title"],
            price=Decimal(str(row["price"])) if row["price"] not in (None, "") else None,
            regular_price=Decimal(str(row["regular_price"])) if row["regular_price"] not in (None, "") else None,
            stock_quantity=int(row["stock_quantity"]) if row["stock_quantity"] not in (None, "") else None,
            image_url=row["image_url"],
        )

    def search_products(self, term: str, limit: int = 5) -> list[ProductRecord]:
        sql = text(
            f"""
            SELECT p.ID AS product_id, sku.meta_value AS sku, p.post_title AS title,
                   price.meta_value AS price, stock.meta_value AS stock_quantity
            FROM {self.prefix}posts p
            LEFT JOIN {self.prefix}postmeta sku ON sku.post_id = p.ID AND sku.meta_key = '_sku'
            LEFT JOIN {self.prefix}postmeta price ON price.post_id = p.ID AND price.meta_key = '_price'
            LEFT JOIN {self.prefix}postmeta stock ON stock.post_id = p.ID AND stock.meta_key = '_stock'
            WHERE p.post_type = 'product' AND p.post_status = 'publish'
              AND (p.post_title LIKE :term OR sku.meta_value = :sku)
            ORDER BY p.post_modified_gmt DESC
            LIMIT :limit
            """
        )
        with self.connection() as conn:
            rows = conn.execute(sql, {"term": f"%{term}%", "sku": term, "limit": limit}).mappings().all()
        return [
            ProductRecord(
                product_id=int(row["product_id"]),
                sku=row["sku"] or "",
                title=row["title"],
                price=Decimal(str(row["price"])) if row["price"] not in (None, "") else None,
                regular_price=None,
                stock_quantity=int(row["stock_quantity"]) if row["stock_quantity"] not in (None, "") else None,
            )
            for row in rows
        ]

    def recent_product_events(self, minutes: int = 15) -> list[ProductRecord]:
        sql = text(
            f"""
            SELECT p.ID AS product_id, sku.meta_value AS sku, p.post_title AS title,
                   price.meta_value AS price, stock.meta_value AS stock_quantity
            FROM {self.prefix}posts p
            LEFT JOIN {self.prefix}postmeta sku ON sku.post_id = p.ID AND sku.meta_key = '_sku'
            LEFT JOIN {self.prefix}postmeta price ON price.post_id = p.ID AND price.meta_key = '_price'
            LEFT JOIN {self.prefix}postmeta stock ON stock.post_id = p.ID AND stock.meta_key = '_stock'
            WHERE p.post_type = 'product' AND p.post_status = 'publish'
              AND p.post_modified_gmt >= UTC_TIMESTAMP() - INTERVAL :minutes MINUTE
            ORDER BY p.post_modified_gmt DESC
            """
        )
        with self.connection() as conn:
            rows = conn.execute(sql, {"minutes": minutes}).mappings().all()
        return [
            ProductRecord(
                product_id=int(row["product_id"]),
                sku=row["sku"] or "",
                title=row["title"],
                price=Decimal(str(row["price"])) if row["price"] not in (None, "") else None,
                regular_price=None,
                stock_quantity=int(row["stock_quantity"]) if row["stock_quantity"] not in (None, "") else None,
            )
            for row in rows
        ]

    def unprocessed_event_products(self, limit: int = 25) -> list[ProductRecord]:
        sql = text(
            f"""
            SELECT DISTINCT e.product_id, sku.meta_value AS sku, p.post_title AS title,
                   price.meta_value AS price, stock.meta_value AS stock_quantity
            FROM {self.prefix}product_automation_events e
            JOIN {self.prefix}posts p ON p.ID = e.product_id
            LEFT JOIN {self.prefix}postmeta sku ON sku.post_id = p.ID AND sku.meta_key = '_sku'
            LEFT JOIN {self.prefix}postmeta price ON price.post_id = p.ID AND price.meta_key = '_price'
            LEFT JOIN {self.prefix}postmeta stock ON stock.post_id = p.ID AND stock.meta_key = '_stock'
            WHERE e.processed_at IS NULL AND p.post_status = 'publish'
            ORDER BY e.created_at ASC
            LIMIT :limit
            """
        )
        with self.connection() as conn:
            rows = conn.execute(sql, {"limit": limit}).mappings().all()
        return [
            ProductRecord(
                product_id=int(row["product_id"]),
                sku=row["sku"] or "",
                title=row["title"],
                price=Decimal(str(row["price"])) if row["price"] not in (None, "") else None,
                regular_price=None,
                stock_quantity=int(row["stock_quantity"]) if row["stock_quantity"] not in (None, "") else None,
            )
            for row in rows
        ]

    def mark_events_processed(self, product_ids: list[int]) -> None:
        if not product_ids:
            return
        sql = text(
            f"""
            UPDATE {self.prefix}product_automation_events
            SET processed_at = UTC_TIMESTAMP()
            WHERE processed_at IS NULL AND product_id IN :product_ids
            """
        ).bindparams(bindparam("product_ids", expanding=True))
        with self.connection() as conn:
            conn.execute(sql, {"product_ids": product_ids})

    def product_audit_checksum(self) -> str:
        sql = text(
            f"""
            SELECT SHA2(GROUP_CONCAT(CONCAT_WS(':', p.ID, p.post_modified_gmt, COALESCE(pm.meta_value, ''))
                        ORDER BY p.ID SEPARATOR '|'), 256) AS checksum
            FROM {self.prefix}posts p
            LEFT JOIN {self.prefix}postmeta pm ON pm.post_id = p.ID AND pm.meta_key IN ('_price','_stock')
            WHERE p.post_type IN ('product','product_variation')
            """
        )
        with self.connection() as conn:
            row = conn.execute(sql).mappings().first()
        return row["checksum"] or "empty"
