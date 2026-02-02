"""
Scraper de Carrefour.

Obtiene productos desde la API de Carrefour y los normaliza al contrato común.
La respuesta de productos devuelve el campo "impressions" como string JSON;
hay que parsearlo y formatear el nombre desde slug.

Si Carrefour devuelve 403: el scraper usa curl_cffi (TLS tipo Chrome) cuando está
instalado; si no, headers de navegador y visita previa a /supermercado/. Opcional:
inyecta cookies con CARREFOUR_COOKIES (ver _inject_cookies_from_env).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from ..base import BaseScraper
from ..categories import CategoryMapper
from ..http_client import HttpClient
from ..models import Category, NormalizedProduct, RawProduct

try:
    from ..http_client_curl_cffi import CurlCffiClient, CURL_CFFI_AVAILABLE
except ImportError:
    CurlCffiClient = None
    CURL_CFFI_AVAILABLE = False

logger = logging.getLogger(__name__)


class CarrefourScraper(BaseScraper):
    """Scraper para el supermercado Carrefour."""

    MARKET = "carrefour"

    CATEGORIES_URL = (
        "https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu"
        "?sale_point=005290&depth=1&current_category=foodRootCategory&limit=3&lang=es&freelink=true"
    )
    PLP_BASE_URL = "https://www.carrefour.es/cloud-api/plp-food-analytics/v1"
    BASE_URL = "https://www.carrefour.es"

    # Headers tipo navegador para evitar 403 (Carrefour bloquea peticiones sin Referer/Origin)
    BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Origin": "https://www.carrefour.es",
        "Referer": "https://www.carrefour.es/supermercado/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    def __init__(self, http_client: Optional[HttpClient] = None):
        """Inicializa el scraper de Carrefour."""
        if http_client is None:
            if CURL_CFFI_AVAILABLE and CurlCffiClient is not None:
                try:
                    http_client = CurlCffiClient(headers=self.BROWSER_HEADERS)
                    logger.info("Usando curl_cffi (TLS tipo Chrome) para Carrefour")
                except Exception as e:
                    logger.warning(f"curl_cffi no disponible, usando requests: {e}")
                    http_client = HttpClient(headers=self.BROWSER_HEADERS)
            else:
                http_client = HttpClient(headers=self.BROWSER_HEADERS)
        super().__init__(http_client)
        self.category_mapper = CategoryMapper(self.MARKET)
        self._session_warmed = False
        self._inject_cookies_from_env()

    def _inject_cookies_from_env(self) -> None:
        """
        Inyecta cookies desde la variable de entorno CARREFOUR_COOKIES.

        Si Carrefour devuelve 403, puedes copiar las cookies del navegador
        (DevTools > Application > Cookies > www.carrefour.es) y exportarlas como
        "nombre=valor; nombre2=valor2". Luego ejecuta:
            export CARREFOUR_COOKIES="nombre=valor; nombre2=valor2"
            python3 main.py scrape carrefour --test --dry-run
        """
        raw = os.environ.get("CARREFOUR_COOKIES", "").strip()
        if not raw:
            return
        # requests: session.cookies.set(name, value, domain=..., path=...)
        # curl_cffi: no tiene .set() con domain/path, usamos header Cookie
        cookies = getattr(self.http.session, "cookies", None)
        if cookies is not None and callable(getattr(cookies, "set", None)):
            for part in raw.split(";"):
                part = part.strip()
                if "=" not in part:
                    continue
                name, _, value = part.partition("=")
                name, value = name.strip(), value.strip()
                if name:
                    self.http.session.cookies.set(
                        name, value, domain=".carrefour.es", path="/"
                    )
        else:
            self.http.session.headers["Cookie"] = raw
        logger.info("Cookies inyectadas desde CARREFOUR_COOKIES")

    def _ensure_session(self) -> None:
        """Visita la página del supermercado para obtener cookies y evitar 403."""
        if self._session_warmed:
            return
        try:
            url = f"{self.BASE_URL}/supermercado/"
            logger.debug(f"Obteniendo cookies desde {url}")
            kwargs = {"timeout": self.http.timeout}
            if hasattr(self.http, "impersonate"):
                kwargs["impersonate"] = self.http.impersonate
            self.http.session.get(url, **kwargs)
            self._session_warmed = True
        except Exception as e:
            logger.warning(f"No se pudieron obtener cookies: {e}")

    def get_categories(self) -> List[Category]:
        """
        Obtiene el árbol de categorías de Carrefour.

        Returns:
            Lista de subcategorías (hijas de la sección Supermercado).
        """
        if self._categories_cache is not None:
            return self._categories_cache

        self._ensure_session()
        logger.info(f"Obteniendo categorías de {self.CATEGORIES_URL}")
        data = self.http.get(self.CATEGORIES_URL, use_cache=True)

        if not data:
            logger.error("No se pudo obtener el menú de categorías")
            return []

        data = data.get("result", data)
        menu = data.get("menu", [])

        if not menu:
            logger.warning("Menú vacío")
            return []

        section = menu[0].get("childs", [])
        if not section:
            logger.warning("Sin sección supermercado en el menú")
            return []

        parent = section[0]
        parent_name = parent.get("name") or (parent.get("analytics") or {}).get(
            "title", "supermercado"
        )
        if isinstance(parent_name, str):
            parent_name = parent_name.title()

        categories = []
        for child in parent.get("childs", []):
            external_id = child.get("id")
            name = child.get("name")

            if not external_id or not name:
                continue

            link = child.get("url_rel", "") or ""
            link = link.lstrip("/") or str(external_id)

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

        La API devuelve "impressions" como string JSON; se parsea y se
        extrae la lista de productos.

        Args:
            category: Categoría a scrapear.

        Returns:
            Lista de productos crudos.
        """
        self._ensure_session()
        path = category.link.lstrip("/")
        url = f"{self.PLP_BASE_URL}/{path}"
        logger.debug(f"Descargando PLP: {url}")

        data = self.http.get(url)
        if not data:
            logger.warning(f"No se pudo descargar PLP de {category}")
            return []

        data = data.get("result", data)
        impressions_raw = data.get("impressions")

        if impressions_raw is None:
            logger.warning(f"Sin campo impressions en respuesta de {category}")
            return []

        if isinstance(impressions_raw, str):
            try:
                items = json.loads(impressions_raw)
            except json.JSONDecodeError as e:
                logger.error(f"Error al parsear impressions: {e}")
                return []
        elif isinstance(impressions_raw, list):
            items = impressions_raw
        else:
            logger.warning("impressions no es string ni lista")
            return []

        raw_products = []
        for item in items:
            item_id = item.get("item_id")
            if item_id is None:
                continue
            raw_products.append(
                RawProduct(raw_id=str(item_id), raw_data=item)
            )

        logger.debug(f"Productos encontrados en {category.name}: {len(raw_products)}")
        return raw_products

    def _slug_to_display_name(self, slug: str) -> str:
        """Convierte un slug (item_name) a nombre legible con título."""
        if not slug:
            return ""
        return slug.replace("-", " ").strip().title()

    def scrape_pdp(self, product_url: str) -> Dict[str, Any]:
        """
        Fase B - PDP: Enriquecimiento desde página de detalle.

        TODO: Implementar cuando se necesite.
        """
        raise NotImplementedError("PDP no implementado para Carrefour")

    def normalize(
        self,
        raw_product: RawProduct,
        category: Category,
    ) -> Optional[NormalizedProduct]:
        """
        Transforma un producto crudo de Carrefour al formato normalizado.

        Args:
            raw_product: Producto crudo de la API (ítem del array impressions).
            category: Categoría del producto.

        Returns:
            Producto normalizado o None si no es válido.
        """
        item = raw_product.raw_data
        display_name = self._slug_to_display_name(item.get("item_name") or "")

        if not display_name:
            return None

        price = item.get("price")
        try:
            price_float = float(price) if price is not None else None
        except (TypeError, ValueError):
            price_float = None

        unique_id = f"{self.MARKET}_{raw_product.raw_id}"
        master_category_id = self.category_mapper.get_master_category(category)

        return NormalizedProduct(
            id=unique_id,
            name=display_name,
            supermarket=self.MARKET,
            category=str(category),
            master_category_id=master_category_id,
            price=price_float,
            price_per_unit=None,
            unit=None,
            brand=item.get("item_brand"),
            url="",
            image_url="",
        )

    def save_category_mappings(self) -> None:
        """Guarda los mapeos de categorías al archivo JSON."""
        self.category_mapper.save_mappings()
