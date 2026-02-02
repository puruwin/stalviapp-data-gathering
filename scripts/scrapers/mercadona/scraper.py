"""
Scraper de Mercadona.

Obtiene productos desde la API de Mercadona y los normaliza al contrato común.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseScraper
from ..categories import CategoryMapper
from ..http_client import HttpClient
from ..models import Category, NormalizedProduct, RawProduct

logger = logging.getLogger(__name__)


class MercadonaScraper(BaseScraper):
    """Scraper para el supermercado Mercadona."""

    MARKET = "mercadona"

    # URLs de la API
    CATEGORIES_URL = "https://tienda.mercadona.es/api/categories/?lang=es&wh=alc1"
    CATEGORY_DETAIL_URL = "https://tienda.mercadona.es/api/categories/{category_id}/?lang=es&wh=alc1"
    BASE_URL = "https://tienda.mercadona.es"

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Inicializa el scraper de Mercadona."""
        super().__init__(http_client)
        self.category_mapper = CategoryMapper(self.MARKET)

    def get_categories(self) -> List[Category]:
        """
        Obtiene el árbol de categorías de Mercadona.

        Returns:
            Lista de subcategorías (hijas de categorías principales).
        """
        if self._categories_cache is not None:
            return self._categories_cache

        logger.info(f"Obteniendo categorías de {self.CATEGORIES_URL}")
        data = self.http.get(self.CATEGORIES_URL, use_cache=True)

        if not data:
            logger.error("No se pudo obtener el árbol de categorías")
            return []

        categories = []
        for parent in data.get("results", []):
            parent_name = parent.get("name", "Sin nombre")

            for child in parent.get("categories", []):
                if not child.get("published", True):
                    continue

                external_id = child.get("id")
                name = child.get("name")

                if external_id is None or not name:
                    continue

                categories.append(
                    Category(
                        id=str(external_id),
                        name=name,
                        parent_name=parent_name,
                        link=str(external_id),
                    )
                )

        logger.info(f"Categorías obtenidas: {len(categories)}")
        self._categories_cache = categories
        return categories

    def scrape_plp(self, category: Category) -> List[RawProduct]:
        """
        Descarga productos de una categoría (PLP).

        Args:
            category: Categoría a scrapear.

        Returns:
            Lista de productos crudos.
        """
        url = self.CATEGORY_DETAIL_URL.format(category_id=category.id)
        logger.debug(f"Descargando PLP: {url}")

        data = self.http.get(url)
        if not data:
            logger.warning(f"No se pudo descargar PLP de {category}")
            return []

        raw_products = []
        for subcat in data.get("categories", []):
            for item in subcat.get("products", []):
                product_id = item.get("id")
                if product_id is None:
                    continue
                raw_products.append(
                    RawProduct(
                        raw_id=str(product_id),
                        raw_data=item,
                    )
                )

        logger.debug(f"Productos encontrados en {category.name}: {len(raw_products)}")
        return raw_products

    def scrape_pdp(self, product_url: str) -> Dict[str, Any]:
        """
        Fase B - PDP: Enriquecimiento desde página de detalle.

        TODO: Implementar cuando se necesite.
        """
        raise NotImplementedError("PDP no implementado para Mercadona")

    def normalize(
        self,
        raw_product: RawProduct,
        category: Category,
    ) -> Optional[NormalizedProduct]:
        """
        Transforma un producto crudo de Mercadona al formato normalizado.

        Args:
            raw_product: Producto crudo de la API.
            category: Categoría del producto.

        Returns:
            Producto normalizado o None si no es válido.
        """
        item = raw_product.raw_data
        display_name = item.get("display_name")

        if not display_name:
            return None

        price_instructions = item.get("price_instructions") or {}
        bulk_price = price_instructions.get("bulk_price")
        unit_price = price_instructions.get("unit_price") or price_instructions.get(
            "reference_price"
        )
        unit = price_instructions.get("reference_format") or price_instructions.get(
            "size_format"
        )

        try:
            price = float(bulk_price) if bulk_price is not None else None
        except (TypeError, ValueError):
            price = None

        try:
            price_per_unit = float(unit_price) if unit_price is not None else None
        except (TypeError, ValueError):
            price_per_unit = None

        unique_id = f"{self.MARKET}_{raw_product.raw_id}"
        master_category_id = self.category_mapper.get_master_category(category)

        return NormalizedProduct(
            id=unique_id,
            name=display_name,
            supermarket=self.MARKET,
            category=str(category),
            master_category_id=master_category_id,
            price=price,
            price_per_unit=price_per_unit,
            unit=unit,
            brand=None,
            url=item.get("share_url") or "",
            image_url=item.get("thumbnail") or "",
        )

    def save_category_mappings(self) -> None:
        """Guarda los mapeos de categorías al archivo JSON."""
        self.category_mapper.save_mappings()
