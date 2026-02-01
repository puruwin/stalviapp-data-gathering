"""
Scraper de DIA.

Obtiene productos desde la API de DIA y los normaliza al contrato común.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseScraper
from ..categories import CategoryMapper
from ..http_client import HttpClient
from ..models import Category, NormalizedProduct, RawProduct

logger = logging.getLogger(__name__)


class DiaScraper(BaseScraper):
    """Scraper para el supermercado DIA."""

    MARKET = "dia"

    # URLs de la API
    CATEGORIES_URL = "https://www.dia.es/api/v1/common-aggregator/menu-data"
    PLP_BASE_URL = "https://www.dia.es/api/v1/plp-back/reduced"
    BASE_URL = "https://www.dia.es"

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Inicializa el scraper de DIA."""
        super().__init__(http_client)
        self.category_mapper = CategoryMapper(self.MARKET)

    def get_categories(self) -> List[Category]:
        """
        Obtiene el árbol de categorías de DIA.

        Returns:
            Lista de subcategorías (hijas de categorías principales).
        """
        # Usar cache si ya se obtuvieron
        if self._categories_cache is not None:
            return self._categories_cache

        logger.info(f"Obteniendo categorías de {self.CATEGORIES_URL}")
        data = self.http.get(self.CATEGORIES_URL, use_cache=True)

        if not data:
            logger.error("No se pudo obtener el árbol de categorías")
            return []

        categories = []
        for categoria_principal in data.get("categories", []):
            parent_name = categoria_principal.get("name", "Sin nombre")

            for child in categoria_principal.get("children", []):
                external_id = child.get("id")
                name = child.get("name")
                link = child.get("link")

                if not external_id or not name or not link:
                    continue

                # Omitir categorías "Todo X" (son agregadores)
                if name.startswith("Todo "):
                    logger.debug(f"Omitiendo categoría agregadora: {name}")
                    continue

                categories.append(
                    Category(
                        id=str(external_id),
                        name=name,
                        parent_name=parent_name,
                        link=link,
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
        url = f"{self.PLP_BASE_URL}{category.link}"
        logger.debug(f"Descargando PLP: {url}")

        data = self.http.get(url)
        if not data:
            logger.warning(f"No se pudo descargar PLP de {category}")
            return []

        plp_items = data.get("plp_items", [])
        logger.debug(f"Productos encontrados en {category.name}: {len(plp_items)}")

        return [
            RawProduct(
                raw_id=self._extract_id(item),
                raw_data=item,
            )
            for item in plp_items
            if self._extract_id(item)
        ]

    def scrape_pdp(self, product_url: str) -> Dict[str, Any]:
        """
        Fase B - PDP: Enriquecimiento desde página de detalle.

        TODO: Implementar cuando se necesite enriquecimiento.
        """
        raise NotImplementedError("PDP no implementado para DIA")

    def normalize(
        self,
        raw_product: RawProduct,
        category: Category,
    ) -> Optional[NormalizedProduct]:
        """
        Transforma un producto crudo de DIA al formato normalizado.

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

        # Extraer precios
        prices = item.get("prices", {}) or {}
        price = prices.get("price")
        price_per_unit = prices.get("price_per_unit")
        measure_unit = prices.get("measure_unit")

        # Extraer otros campos
        brand = item.get("brand")
        product_url = item.get("url") or item.get("link") or ""
        image_url = item.get("image") or item.get("image_url") or ""

        # Generar ID único
        unique_id = f"{self.MARKET}_{raw_product.raw_id}"

        # Obtener categoría maestra normalizada
        master_category_id = self.category_mapper.get_master_category(category)

        return NormalizedProduct(
            id=unique_id,
            name=display_name,
            supermarket=self.MARKET,
            category=str(category),
            master_category_id=master_category_id,
            price=price,
            price_per_unit=price_per_unit,
            unit=measure_unit,
            brand=brand,
            url=product_url,
            image_url=image_url,
        )
    
    def save_category_mappings(self) -> None:
        """Guarda los mapeos de categorías al archivo JSON."""
        self.category_mapper.save_mappings()

    def _extract_id(self, item: Dict[str, Any]) -> str:
        """Extrae el ID del producto de los datos crudos."""
        product_id = item.get("id") or item.get("product_id") or item.get("sku")
        if product_id:
            return str(product_id)

        # Fallback: usar hash del nombre
        display_name = item.get("display_name", "")
        if display_name:
            return str(hash(display_name))

        return ""
