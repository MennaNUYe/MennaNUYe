"""WooCommerce REST API client."""
from __future__ import annotations

from decimal import Decimal

from automation.core.config import AutomationConfig, require_env
from automation.core.http import build_session


class WooCommerceClient:
    def __init__(self, config: AutomationConfig):
        require_env(["WC_BASE_URL", "WC_CONSUMER_KEY", "WC_CONSUMER_SECRET"])
        self.config = config
        self.session = build_session()
        self.auth = (config.woocommerce.consumer_key, config.woocommerce.consumer_secret)
        self.api_base = f"{config.woocommerce.base_url}/wp-json/wc/v3"

    def find_product_by_sku(self, sku: str) -> dict | None:
        response = self.session.get(
            f"{self.api_base}/products",
            params={"sku": sku, "per_page": 1},
            auth=self.auth,
            timeout=self.config.woocommerce.timeout_seconds,
        )
        response.raise_for_status()
        products = response.json()
        return products[0] if products else None

    def update_product(self, product_id: int, price: Decimal, stock_quantity: int | None = None) -> dict:
        payload: dict[str, str | int | bool] = {"regular_price": str(price), "price": str(price)}
        if stock_quantity is not None:
            payload.update({"manage_stock": True, "stock_quantity": stock_quantity})
        response = self.session.put(
            f"{self.api_base}/products/{product_id}",
            json=payload,
            auth=self.auth,
            timeout=self.config.woocommerce.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
