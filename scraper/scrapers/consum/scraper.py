"""Catálogo anónimo de Consum: hojas del menú, paginación por offset y precios EUR."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

from ..base import BaseScraper
from ..categories import CategoryMapper
from ..http_client import HttpClient
from ..models import Category, NormalizedProduct, RawProduct


class ConsumScraper(BaseScraper):
    MARKET = "consum"
    BASE_URL = "https://tienda.consum.es"
    CATEGORIES_URL = BASE_URL + "/api/rest/V1.0/shopping/category/menu"
    PRODUCT_BASE_URL = BASE_URL + "/api/rest/V1.0/catalog/product"
    PRICE_CONTEXT = "consum:online:anonymous:zone-unspecified:EUR"
    MAX_PAGES = 1000

    def __init__(self, http_client=None, max_products_per_category=None, price_context=None):
        super().__init__(http_client or HttpClient(headers={
            "User-Agent": "Stalviapp/0.1 (catalogue scraper)",
            "Accept-Language": "es-ES,es;q=0.9",
        }))
        self.category_mapper = CategoryMapper(self.MARKET)
        self.max_products_per_category = max_products_per_category
        self.price_context = price_context or self.PRICE_CONTEXT

    def get_categories(self):
        if self._categories_cache is not None:
            return self._categories_cache
        data = self.http.get(self.CATEGORIES_URL, use_cache=True)
        if isinstance(data, dict):
            data = data.get("result")
        if not isinstance(data, list) or not data:
            raise RuntimeError("Consum: menú ausente o con formato inesperado")
        categories = {}

        def visit(nodes, parents=()):
            if not isinstance(nodes, list):
                raise RuntimeError("Consum: subcategorías con formato inesperado")
            for node in nodes:
                if not isinstance(node, dict):
                    raise RuntimeError("Consum: categoría inválida")
                # Excluir campañas y categorías virtuales para evitar duplicados.
                if node.get("type", 0) != 0:
                    continue
                name = node.get("name") or node.get("nombre")
                if node.get("id") is None or not name:
                    raise RuntimeError("Consum: categoría sin ID o nombre")
                children = node.get("subcategories", [])
                if children:
                    visit(children, parents + (name,))
                else:
                    key = str(node["id"])
                    categories.setdefault(key, Category(
                        id=key, name=name, parent_name=" > ".join(parents),
                        link=urljoin(self.BASE_URL, node.get("url") or f"/es/c/{key}"),
                    ))

        visit(data)
        if not categories:
            raise RuntimeError("Consum: menú sin categorías de catálogo")
        self._categories_cache = list(categories.values())
        for category in self._categories_cache:
            self.category_mapper.register_pending(category)
        return self._categories_cache

    def scrape_plp(self, category):
        products = {}
        seen_ids = set()
        offset = 0
        for _ in range(self.MAX_PAGES):
            query = urlencode({
                "page": 1, "offset": offset, "orderById": 5,
                "showProducts": "true", "showRecommendations": "false",
                "categories": category.id,
            })
            data = self.http.get(f"{self.PRODUCT_BASE_URL}?{query}")
            if isinstance(data, dict):
                data = data.get("result", data)
            if not isinstance(data, dict):
                raise RuntimeError(f"Consum {category.id}: fallo al descargar offset={offset}")
            items, has_more = data.get("products"), data.get("hasMore")
            total = data.get("totalCount")
            if (not isinstance(items, list) or type(has_more) is not bool
                    or type(total) is not int or total < 0):
                raise RuntimeError(f"Consum {category.id}: respuesta de paginación inválida")
            previous_count = len(seen_ids)
            for item in items:
                if not isinstance(item, dict) or item.get("id") is None or not item.get("code"):
                    raise RuntimeError(f"Consum {category.id}: producto sin ID/SKU")
                seen_ids.add(str(item["id"]))
                code = str(item["code"])
                products.setdefault(code, RawProduct(raw_id=code, raw_data=item))
            if items and len(seen_ids) == previous_count:
                raise RuntimeError(f"Consum {category.id}: página repetida en offset={offset}")
            limit = self.max_products_per_category
            if limit and len(products) >= limit:
                return list(products.values())[:limit]
            if not has_more:
                # totalCount cuenta filas, incluidos patrocinados repetidos.
                # La cobertura se contrasta antes de deduplicar por identidad.
                if offset + len(items) < total:
                    raise RuntimeError(f"Consum {category.id}: catálogo truncado ({offset + len(items)}/{total})")
                return list(products.values())
            if not items:
                raise RuntimeError(f"Consum {category.id}: página vacía con hasMore=true")
            offset += len(items)
            self.http.delay()
        raise RuntimeError(f"Consum {category.id}: límite de páginas excedido")

    @staticmethod
    def _amount(value):
        # centAmount contiene euros, incluso para importes enteros >= 100.
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number >= 0 else None

    @staticmethod
    def _active(entry, now, start="from", end="to"):
        try:
            lower = datetime.fromisoformat(entry[start].replace("Z", "+00:00")) if entry.get(start) else None
            upper = datetime.fromisoformat(entry[end].replace("Z", "+00:00")) if entry.get(end) else None
            return (lower is None or lower <= now) and (upper is None or now <= upper)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _reference_unit(label, amount):
        match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|lv|unidad(?:es)?|ud\.?)\s*", label or "", re.I)
        if not match:
            return label or None, amount
        quantity, unit = float(match[1].replace(",", ".")), match[2].lower()
        if quantity <= 0:
            return label, amount
        if unit in ("g", "ml"):
            quantity /= 1000
        unit = {"g": "kg", "ml": "l", "lv": "lavado"}.get(unit, unit)
        if unit.startswith(("unidad", "ud")):
            unit = "ud"
        return unit, round(amount / quantity, 4) if amount is not None else None

    def normalize(self, raw_product, category, observed_at=None):
        item = raw_product.raw_data
        pd, prices_data = item.get("productData") or {}, item.get("priceData") or {}
        name = pd.get("description") or pd.get("name")
        if not name:
            raise ValueError(f"Consum {raw_product.raw_id}: producto sin nombre")
        now = observed_at or datetime.now(timezone.utc)
        prices = {p["id"]: p for p in prices_data.get("prices", [])
                  if self._active(p, now, start="fromDate", end="toDate")}
        selected = prices.get("PRICE", {})
        offer = prices.get("OFFER_PRICE")
        # Solo precio directo de una unidad; sin descontar cheque, club ni multicompras.
        immediate = any(
            p.get("inmediate") is True and p.get("promotionType") == 1
            and p.get("applicationTargetType") == 1 and p.get("applicationActionType") == 2
            and self._active(p, now)
            and self._amount(p.get("amount")) is not None
            and self._amount(p.get("amount")) == self._amount((offer or {}).get("value", {}).get("centAmount"))
            for p in item.get("offers", [])
        )
        if offer and immediate:
            selected = offer
        values = selected.get("value") or {}
        price = self._amount(values.get("centAmount"))
        ppu = self._amount(values.get("centUnitAmount"))
        if price is None or price <= 0:
            raise ValueError(f"Consum {raw_product.raw_id}: precio ausente o inválido")
        unit, ppu = self._reference_unit(prices_data.get("unitPriceUnitType"), ppu)
        brand = pd.get("brand") or {}
        brand = brand.get("name") if isinstance(brand, dict) else str(brand)
        # La URL principal publicada puede devolver 404; la galería ofrece las
        # fotografías reales (..._001.jpg). Mantener las alternativas de origen.
        gallery = sorted(item.get("media") or [], key=lambda m: m.get("order", 999))
        images = list(dict.fromkeys(urljoin(self.BASE_URL, value)
                    for value in [*(m.get("url") for m in gallery), pd.get("imageURL")]
                    if value))
        image = images[0] if images else ""
        return NormalizedProduct(
            id=f"{self.MARKET}_{raw_product.raw_id}", name=name, supermarket=self.MARKET,
            category=str(category), master_category_id=self.category_mapper.get_master_category(category, auto_map=False),
            price=price, price_per_unit=ppu, unit=unit, brand=brand,
            url=urljoin(self.BASE_URL, pd.get("url") or f"/es/p/{raw_product.raw_id}"),
            image_url=urljoin(self.BASE_URL, image) if image else "",
            source_metadata={
                "api_id": item.get("id"), "sku": str(item["code"]), "ean": item.get("ean"),
                "price_context": self.price_context, "currency": "EUR",
                "image_candidates": images,
                "observed_at": now.isoformat(), "source_category_id": category.id,
                "availability": pd.get("availability"),
                "temporary_out_of_stock": pd.get("temporaryOutOfStock"),
                "format": pd.get("format"), "price_data": prices_data,
                "selected_price_id": selected.get("id"),
                "offers": item.get("offers", []), "coupons": item.get("coupons", []),
            },
        )

    def save_category_mappings(self):
        self.category_mapper.save_mappings()
