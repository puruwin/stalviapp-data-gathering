"""
Validación de productos antes de ingesta.

Asegura que los datos cumplan el contrato antes de enviarlos a Firebase.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from .models import NormalizedProduct

logger = logging.getLogger(__name__)

# URLs base por supermercado
BASE_URLS = {
    "dia": "https://www.dia.es",
    "mercadona": "https://tienda.mercadona.es",
}


def validate_product(product: NormalizedProduct) -> Optional[NormalizedProduct]:
    """
    Valida y limpia un producto antes de ingesta.

    Reglas:
    - ID obligatorio (descarta si no existe)
    - Precios convertidos a float o None
    - Strings vacías convertidas a None
    - URLs convertidas a absolutas

    Args:
        product: Producto a validar.

    Returns:
        Producto validado o None si no es válido.
    """
    # ID obligatorio
    if not product.id:
        logger.warning(f"Producto descartado: sin ID - {product.name}")
        return None

    # Nombre obligatorio
    if not product.name:
        logger.warning(f"Producto descartado: sin nombre - {product.id}")
        return None

    # Precios a float o None
    price = _to_float(product.price)
    price_per_unit = _to_float(product.price_per_unit)

    # Strings vacías a None
    brand = _clean_string(product.brand)
    unit = _clean_string(product.unit)

    # URLs absolutas
    url = _ensure_absolute_url(product.url, product.supermarket)
    image_url = _ensure_absolute_url(product.image_url, product.supermarket)

    return NormalizedProduct(
        id=product.id,
        name=product.name,
        supermarket=product.supermarket,
        category=product.category,
        master_category_id=product.master_category_id,
        price=price,
        price_per_unit=price_per_unit,
        unit=unit,
        brand=brand,
        url=url,
        image_url=image_url,
    )


def validate_products(
    products: List[NormalizedProduct],
) -> List[NormalizedProduct]:
    """
    Valida una lista de productos, descartando los inválidos.

    Args:
        products: Lista de productos a validar.

    Returns:
        Lista de productos válidos.
    """
    valid = []
    discarded = 0

    for product in products:
        validated = validate_product(product)
        if validated:
            valid.append(validated)
        else:
            discarded += 1

    if discarded > 0:
        logger.info(f"Productos descartados por validación: {discarded}")

    return valid


def _to_float(value) -> Optional[float]:
    """Convierte un valor a float o None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _clean_string(value: Optional[str]) -> Optional[str]:
    """Convierte strings vacías a None."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _ensure_absolute_url(url: Optional[str], market: str) -> str:
    """Asegura que la URL sea absoluta."""
    if not url:
        return ""
    url = str(url).strip()
    if url.startswith("http"):
        return url
    base = BASE_URLS.get(market, "")
    return f"{base}{url}" if base else url
