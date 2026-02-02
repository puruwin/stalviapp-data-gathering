"""
Cliente HTTP con curl_cffi para imitar TLS de Chrome (evitar 403 por JA3).

Usa la misma interfaz que HttpClient (get, delay, session, timeout) para
poder sustituirlo en scrapers que reciben bloqueos por fingerprint TLS.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    curl_requests = None


class CurlCffiClient:
    """
    Cliente HTTP con TLS tipo Chrome (curl_cffi) para evitar 403 por WAF/JA3.

    Misma interfaz que HttpClient: get(), delay(), session, timeout.
    """

    DEFAULT_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        base_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None,
        impersonate: str = "chrome",
    ):
        """
        Inicializa el cliente con curl_cffi.

        Args:
            timeout: Timeout por request en segundos.
            max_retries: Número máximo de reintentos.
            base_delay: Delay base entre requests en segundos.
            headers: Headers adicionales para las peticiones.
            impersonate: Perfil TLS a imitar ("chrome", "chrome110", etc.).
        """
        if not CURL_CFFI_AVAILABLE:
            raise RuntimeError(
                "curl_cffi no está instalado. Instala con: pip install curl_cffi"
            )
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.impersonate = impersonate
        self.session = curl_requests.Session()
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

        Returns:
            Respuesta JSON o None si falla.
        """
        key = cache_key or url

        if use_cache and key in self._cache:
            logger.debug(f"Cache hit: {key}")
            return self._cache[key]

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"GET {url} (intento {attempt + 1}/{self.max_retries})"
                )
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    impersonate=self.impersonate,
                )

                if response.status_code == 429:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        f"Rate limited (429). Esperando {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

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

                if use_cache:
                    self._cache[key] = data
                    logger.debug(f"Cache guardado: {key}")

                return data

            except Exception as e:
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
