"""
Módulo de ingesta a Firebase.

Envía productos normalizados al endpoint de Firebase Functions.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .models import NormalizedProduct
from .validators import validate_products

logger = logging.getLogger(__name__)

# URL del endpoint de ingesta
FIREBASE_INGEST_URL = os.environ.get(
    "FIREBASE_INGEST_URL",
    "https://ingestproducts-yuggencccq-uc.a.run.app",
)


def ingest_products(
    products: List[NormalizedProduct],
    validate: bool = True,
    batch_size: int = 500,
) -> Optional[Dict[str, Any]]:
    """
    Envía productos a Firebase Functions.

    Args:
        products: Lista de productos normalizados.
        validate: Si True, valida los productos antes de enviar.
        batch_size: Tamaño del lote para envío.

    Returns:
        Respuesta de Firebase con estadísticas o None si falla.
    """
    if not FIREBASE_INGEST_URL:
        logger.error("FIREBASE_INGEST_URL no configurado")
        return None

    if not products:
        logger.warning("No hay productos para enviar")
        return None

    # Validar si corresponde
    if validate:
        products = validate_products(products)
        if not products:
            logger.warning("Ningún producto pasó la validación")
            return None

    # Convertir a diccionarios
    products_data = [p.to_dict() for p in products]

    logger.info(f"Enviando {len(products_data)} productos a Firebase...")

    try:
        response = requests.post(
            FIREBASE_INGEST_URL,
            json={"products": products_data},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"Firebase: {data.get('count', 0)} enviados | "
            f"nuevos: {data.get('new', 0)} | "
            f"actualizados: {data.get('updated', 0)} | "
            f"sin cambios: {data.get('unchanged', 0)}"
        )

        return data

    except requests.RequestException as exc:
        logger.error(f"Error al enviar a Firebase: {exc}")
        return None


def ingest_products_batch(
    products: List[NormalizedProduct],
    batch_size: int = 500,
) -> Dict[str, int]:
    """
    Envía productos en lotes para manejar grandes volúmenes.

    Args:
        products: Lista de productos normalizados.
        batch_size: Tamaño de cada lote.

    Returns:
        Estadísticas totales: new, updated, unchanged, failed.
    """
    stats = {"new": 0, "updated": 0, "unchanged": 0, "failed": 0}

    # Validar todos primero
    products = validate_products(products)
    total = len(products)

    for i in range(0, total, batch_size):
        batch = products[i : i + batch_size]
        logger.info(f"Enviando lote {i // batch_size + 1} ({len(batch)} productos)")

        result = ingest_products(batch, validate=False)

        if result:
            stats["new"] += result.get("new", 0)
            stats["updated"] += result.get("updated", 0)
            stats["unchanged"] += result.get("unchanged", 0)
        else:
            stats["failed"] += len(batch)

    logger.info(
        f"Ingesta completa: {stats['new']} nuevos, "
        f"{stats['updated']} actualizados, "
        f"{stats['unchanged']} sin cambios, "
        f"{stats['failed']} fallidos"
    )

    return stats
