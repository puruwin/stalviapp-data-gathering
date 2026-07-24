"""
Clase base abstracta para scrapers de supermercados.

Define el contrato que todos los scrapers deben implementar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .http_client import HttpClient
from .models import Category, NormalizedProduct, RawProduct


class BaseScraper(ABC):
    """
    Clase base para scrapers de supermercados.

    Cada supermercado debe extender esta clase e implementar
    los métodos abstractos.
    """

    # Nombre del supermercado (debe sobrescribirse)
    MARKET: str = "unknown"

    def __init__(self, http_client: Optional[HttpClient] = None):
        """
        Inicializa el scraper.

        Args:
            http_client: Cliente HTTP a usar. Si no se proporciona,
                        se crea uno con configuración por defecto.
        """
        self.http = http_client or HttpClient()
        self._categories_cache: Optional[List[Category]] = None

    @abstractmethod
    def get_categories(self) -> List[Category]:
        """
        Obtiene el árbol de categorías del supermercado.

        Este método debe implementarse para cada supermercado.
        El resultado se puede cachear en memoria.

        Returns:
            Lista de categorías.
        """
        pass

    @abstractmethod
    def scrape_plp(self, category: Category) -> List[RawProduct]:
        """
        Fase A - PLP: Scraping rápido del listado de productos.

        Obtiene datos básicos: id, nombre, precio, url, imagen.
        Esta es la operación principal, ejecutable frecuentemente.

        Args:
            category: Categoría a scrapear.

        Returns:
            Lista de productos crudos.
        """
        pass

    def scrape_pdp(self, product_url: str) -> Dict:
        """
        Fase B - PDP: Enriquecimiento desde página de detalle.

        Obtiene datos adicionales: ingredientes, alérgenos, formatos.
        Operación lenta, ejecutable 1 vez/día o menos.

        Args:
            product_url: URL del producto.

        Returns:
            Datos adicionales del producto.

        Raises:
            NotImplementedError: Si el scraper no implementa PDP.
        """
        raise NotImplementedError(
            f"scrape_pdp no implementado para {self.MARKET}"
        )

    @abstractmethod
    def normalize(
        self,
        raw_product: RawProduct,
        category: Category,
    ) -> Optional[NormalizedProduct]:
        """
        Transforma un producto crudo al formato normalizado.

        Args:
            raw_product: Producto con datos crudos de la API.
            category: Categoría del producto.

        Returns:
            Producto normalizado o None si no se puede procesar.
        """
        pass

    def scrape_category(
        self,
        category: Category,
    ) -> List[NormalizedProduct]:
        """
        Scrapea una categoría completa: PLP + normalización.

        Args:
            category: Categoría a scrapear.

        Returns:
            Lista de productos normalizados.
        """
        raw_products = self.scrape_plp(category)
        normalized = []

        for raw in raw_products:
            product = self.normalize(raw, category)
            if product:
                normalized.append(product)

        return normalized

    def scrape_all(
        self,
        max_categories: Optional[int] = None,
        max_products_per_category: Optional[int] = None,
    ) -> List[NormalizedProduct]:
        """
        Scrapea todas las categorías del supermercado.

        Args:
            max_categories: Límite de categorías (para testing).
            max_products_per_category: Límite de productos por categoría.

        Returns:
            Lista de todos los productos normalizados.
        """
        categories = self.get_categories()

        if max_categories:
            categories = categories[:max_categories]

        all_products = []

        for category in categories:
            products = self.scrape_category(category)

            if max_products_per_category:
                products = products[:max_products_per_category]

            all_products.extend(products)
            self.http.delay()

        return all_products
