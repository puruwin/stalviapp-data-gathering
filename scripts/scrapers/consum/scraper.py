"""
Scraper de Consum.

Obtiene productos desde la API de Consum y los normaliza al contrato común.
Categorías: árbol recursivo (solo hojas). Productos: paginación por page hasta hasMore=false.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseScraper
from ..categories import CategoryMapper
from ..http_client import HttpClient
from ..models import Category, NormalizedProduct, RawProduct

logger = logging.getLogger(__name__)


class ConsumScraper(BaseScraper):
    """Scraper para el supermercado Consum."""

    MARKET = "consum"

    CATEGORIES_URL = "https://tienda.consum.es/api/rest/V1.0/shopping/category/menu"
    PRODUCT_BASE_URL = "https://tienda.consum.es/api/rest/V1.0/catalog/product"
    BASE_URL = "https://tienda.consum.es"

    PRODUCT_QUERY = (
        "orderById=5&showProducts=true&originProduct=undefined&showRecommendations=false"
    )

    DEFAULT_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://tienda.consum.es/es",
        "X-TOL-LOCALE": "es",
        "X-TOL-ZONE": "0",
        "X-TOL-CHANNEL": "1",
        "X-TOL-CURRENCY": "EUR",
        "X-TOL-SHIPPING-ZONE": "0D",
        "X-TOL-APP": "shop-front",
    }

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Inicializa el scraper de Consum."""
        if http_client is None:
            http_client = HttpClient(headers=self.DEFAULT_HEADERS)
        super().__init__(http_client)
        self.category_mapper = CategoryMapper(self.MARKET)

    def _collect_leaf_categories(
        self,
        nodes: List[Dict[str, Any]],
        parent_name: str,
        out: List[Category],
    ) -> None:
        """Recorre el árbol y añade solo categorías hoja (subcategories vacío)."""
        for node in nodes:
            name = node.get("name") or node.get("nombre") or ""
            external_id = node.get("id")
            subcats = node.get("subcategories") or []

            if not external_id or not name:
                continue

            if not subcats:
                out.append(
                    Category(
                        id=str(external_id),
                        name=name,
                        parent_name=parent_name,
                        link=str(external_id),
                    )
                )
            else:
                self._collect_leaf_categories(subcats, name, out)

    def get_categories(self) -> List[Category]:
        """
        Obtiene las categorías hoja del menú de Consum.

        Returns:
            Lista de categorías sin subcategorías (hojas del árbol).
        """
        if self._categories_cache is not None:
            return self._categories_cache

        logger.info(f"Obteniendo categorías de {self.CATEGORIES_URL}")
        data = self.http.get(self.CATEGORIES_URL, use_cache=True)

        if not data:
            logger.error("No se pudo obtener el menú de categorías")
            return []

        if isinstance(data, dict):
            data = data.get("result", data)
        if not isinstance(data, list):
            logger.warning("Menú de categorías no es una lista")
            return []

        categories: List[Category] = []
        self._collect_leaf_categories(data, "Consum", categories)

        logger.info(f"Categorías obtenidas (solo hojas): {len(categories)}")
        self._categories_cache = categories
        return categories

    def scrape_plp(self, category: Category) -> List[RawProduct]:
        """
        Descarga productos de una categoría (PLP) con paginación.

        Args:
            category: Categoría a scrapear.

        Returns:
            Lista de productos crudos (todas las páginas).
        """
        raw_products: List[RawProduct] = []
        page = 1

        while True:
            url = (
                f"{self.PRODUCT_BASE_URL}?page={page}&offset=0&{self.PRODUCT_QUERY}"
                f"&categories={category.id}"
            )
            logger.debug(f"Descargando PLP página {page}: {url}")

            data = self.http.get(url)
            if not data:
                logger.warning(f"No se pudo descargar PLP de {category} (página {page})")
                break

            data = data.get("result", data)
            if not isinstance(data, dict):
                break

            products = data.get("products") or []
            for item in products:
                product_id = item.get("id")
                if product_id is None:
                    continue
                raw_products.append(
                    RawProduct(raw_id=str(product_id), raw_data=item)
                )

            has_more = data.get("hasMore", False)
            if not has_more:
                break

            page += 1
            self.http.delay()

        logger.debug(f"Productos encontrados en {category.name}: {len(raw_products)}")
        return raw_products

    def scrape_pdp(self, product_url: str) -> Dict[str, Any]:
        """
        Fase B - PDP: Enriquecimiento desde página de detalle.

        TODO: Implementar cuando se necesite.
        """
        raise NotImplementedError("PDP no implementado para Consum")

    def _price_to_float(self, value: Any) -> Optional[float]:
        """Convierte centAmount/centUnitAmount a float (euros)."""
        if value is None:
            return None
        try:
            v = float(value)
            if v >= 100 and v == int(v):
                return round(v / 100.0, 2)
            return v
        except (TypeError, ValueError):
            return None

    def normalize(
        self,
        raw_product: RawProduct,
        category: Category,
    ) -> Optional[NormalizedProduct]:
        """
        Transforma un producto crudo de Consum al formato normalizado.

        Args:
            raw_product: Producto crudo de la API.
            category: Categoría del producto.

        Returns:
            Producto normalizado o None si no es válido.
        """
        item = raw_product.raw_data
        pd = item.get("productData") or {}
        prices_data = item.get("priceData") or {}

        name = pd.get("name")
        if not name:
            return None

        brand = None
        b = pd.get("brand")
        if isinstance(b, dict):
            brand = b.get("name")
        elif b is not None:
            brand = str(b)

        url = pd.get("url") or ""
        image_url = pd.get("imageURL") or ""
        if not image_url and item.get("media"):
            image_url = (item["media"][0].get("url") or "")

        price = None
        price_per_unit = None
        prices_list = prices_data.get("prices") or []
        price_entry = None
        for p in prices_list:
            if p.get("id") == "OFFER_PRICE":
                price_entry = p
                break
        if not price_entry and prices_list:
            price_entry = prices_list[0]
        if price_entry:
            val = price_entry.get("value") or {}
            price = self._price_to_float(val.get("centAmount"))
            price_per_unit = self._price_to_float(val.get("centUnitAmount"))
        unit = prices_data.get("unitPriceUnitType")

        unique_id = f"{self.MARKET}_{raw_product.raw_id}"
        master_category_id = self.category_mapper.get_master_category(category)

        return NormalizedProduct(
            id=unique_id,
            name=name,
            supermarket=self.MARKET,
            category=str(category),
            master_category_id=master_category_id,
            price=price,
            price_per_unit=price_per_unit,
            unit=unit,
            brand=brand,
            url=url,
            image_url=image_url,
        )

    def save_category_mappings(self) -> None:
        """Guarda los mapeos de categorías al archivo JSON."""
        self.category_mapper.save_mappings()
