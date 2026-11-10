"""Small Treg client helpers for product research.

Requires the Treg CLI to be installed and authenticated in the current environment.
The CLI keeps the team token out of this code and injects it into each request.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


class TregClient:
    """Call Treg tools through the authenticated ``treg`` command-line client.

    Set up Treg once before using this class:

    1. Install the CLI: ``curl -fsSL https://treg.to/install.sh | sh``
    2. Sign in interactively: ``treg login`` (complete browser sign-in and select
       the team whose tools and billing should be used).
    3. Run ``treg`` and confirm it reports the expected account and active team.

    This class delegates authentication to the CLI; it does not take or store a
    token. Keep credentials out of source files and version control.
    """

    TIKTOK_SHOP_SEARCH = "tikhub.x.tiktok-shop-web-fetch-search-products-list"

    def __init__(self, *, timeout: float = 45.0) -> None:
        self.timeout = timeout

    def tiktok_shop_products(
        self,
        query: str,
        *,
        top_n: int = 5,
        region: str = "US",
        max_pages: int = 3,
    ) -> dict[str, Any]:
        """Return up to ``top_n`` matching TikTok Shop products by reported sales.

        Each fetched page is a separate Treg call (currently about $0.001/page).
        ``max_pages`` bounds both spend and work; ``truncated`` indicates that
        TikTok reported more pages than this call fetched.
        """
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_n < 0:
            raise ValueError("top_n must be non-negative")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")

        products: list[dict[str, Any]] = []
        page_token: str | None = None
        pages_fetched = 0
        has_more = False

        for _ in range(max_pages):
            args = [
                "treg", "--json", "call", self.TIKTOK_SHOP_SEARCH,
                "--query", f"search_word={query}",
                "--query", f"region={region}",
            ]
            if page_token:
                args.extend(["--query", f"page_token={page_token}"])

            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if completed.returncode:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(f"Treg call failed: {detail}")
            envelope = json.loads(completed.stdout)
            response = envelope.get("result", envelope)
            data = response.get("data", {})
            # TikHub wraps the actual search payload in a second data object.
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                data = data["data"]

            page_products = data.get("products", []) if isinstance(data, dict) else []
            products.extend(self._compact_product(item) for item in page_products)
            pages_fetched += 1
            has_more = bool(data.get("has_more", False)) if isinstance(data, dict) else False
            load_more = data.get("load_more_params", {}) if isinstance(data, dict) else {}
            next_token = load_more.get("page_token") if isinstance(load_more, dict) else None
            if not has_more or not next_token or next_token == page_token:
                has_more = False
                break
            page_token = str(next_token)

        ranked = [p for p in products if p["sold_count"] is not None]
        ranked.sort(key=lambda p: (-p["sold_count"], p["title"].casefold()))
        return {
            "query": query,
            "region": region,
            "sort": "sold_count_desc",
            "pages_fetched": pages_fetched,
            "truncated": has_more,
            "products": ranked[:top_n],
        }

    def tester(self) -> dict[str, Any]:
        """Run a low-cost example search and return its compact result."""
        return self.tiktok_shop_products(
            "nail polish",
            top_n=5,
            region="US",
            max_pages=1,
        )

    @staticmethod
    def _compact_product(item: dict[str, Any]) -> dict[str, Any]:
        price_info = item.get("product_price_info") or {}
        rate_info = item.get("rate_info") or {}
        sold_info = item.get("sold_info") or {}
        seller_info = item.get("seller_info") or {}
        seo_url = item.get("seo_url") or {}
        sold_value = sold_info.get("sold_count")
        try:
            sold_count = int(sold_value) if sold_value is not None else None
        except (TypeError, ValueError):
            sold_count = None

        return {
            "product_id": item.get("product_id"),
            "title": item.get("title", ""),
            "price": price_info.get("sale_price_format"),
            "currency": price_info.get("currency_name"),
            "sold_count": sold_count,
            "rating": rate_info.get("score"),
            "review_count": rate_info.get("review_count"),
            "shop": seller_info.get("shop_name"),
            "url": seo_url.get("canonical_url"),
        }
