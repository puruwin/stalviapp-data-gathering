"""
Cliente HTTP robusto con retry, backoff y cache.

Proporciona una capa de abstracción sobre requests con:
- Timeout configurable
- Reintentos con backoff exponencial
- Manejo de rate limiting (429)
- Cache en memoria para categorías
- Logging estructurado
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class HttpClient:
    """Cliente HTTP con retry y backoff."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        base_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Inicializa el cliente HTTP.

        Args:
            timeout: Timeout por request en segundos.
            max_retries: Número máximo de reintentos.
            base_delay: Delay base entre requests en segundos.
            headers: Headers adicionales para las peticiones.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)
        self._cache: Dict[str, Any] = {}

    def get(
        self,
        url: str,
        use_cache: bool = False,
        cache_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Realiza una petición GET con retry y backoff.

        Args:
            url: URL a consultar.
            use_cache: Si True, busca/guarda en cache.
            cache_key: Clave para el cache (default: url).

        Returns:
            Respuesta JSON o None si falla.
        """
        key = cache_key or url

        # Verificar cache
        if use_cache and key in self._cache:
            logger.debug(f"Cache hit: {key}")
            return self._cache[key]

        # Intentar con retry
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"GET {url} (intento {attempt + 1}/{self.max_retries})")
                response = self.session.get(url, timeout=self.timeout)

                # Rate limiting
                if response.status_code == 429:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited (429). Esperando {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Otros errores de servidor
                if response.status_code >= 500:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Error de servidor ({response.status_code}). "
                        f"Reintentando en {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Guardar en cache si corresponde
                if use_cache:
                    self._cache[key] = data
                    logger.debug(f"Cache guardado: {key}")

                return data

            except requests.Timeout:
                logger.warning(f"Timeout en {url} (intento {attempt + 1})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

            except requests.RequestException as e:
                logger.error(f"Error en GET {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        logger.error(f"Falló después de {self.max_retries} intentos: {url}")
        return None

    def clear_cache(self) -> None:
        """Limpia el cache en memoria."""
        self._cache.clear()
        logger.debug("Cache limpiado")

    def delay(self) -> None:
        """Aplica el delay base entre requests."""
        time.sleep(self.base_delay)
