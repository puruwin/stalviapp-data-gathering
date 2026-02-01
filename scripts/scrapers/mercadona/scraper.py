"""
Scraper de Mercadona.

TODO: Implementar cuando se complete DIA.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseScraper
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

    def get_categories(self) -> List[Category]:
        """
        Obtiene el árbol de categorías de Mercadona.

        TODO: Implementar.
        """
        raise NotImplementedError("Mercadona scraper pendiente de implementar")

    def scrape_plp(self, category: Category) -> List[RawProduct]:
        """
        Descarga productos de una categoría (PLP).

        TODO: Implementar.
        """
        raise NotImplementedError("Mercadona scraper pendiente de implementar")

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

        TODO: Implementar.
        """
        raise NotImplementedError("Mercadona scraper pendiente de implementar")
