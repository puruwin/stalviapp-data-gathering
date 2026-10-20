"""
Capa de persistencia a Postgres (psycopg3).

Reemplaza la antigua ingesta a Firebase. Hace upsert idempotente de productos y
registra el histórico de precios: una fila por producto nuevo (baseline) y otra
por cada cambio de precio detectado.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Dict, List, Optional

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

if TYPE_CHECKING:
    from scrapers.models import NormalizedProduct

load_dotenv()
logger = logging.getLogger(__name__)


def get_dsn() -> str:
    """Devuelve la cadena de conexión desde DATABASE_URL."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL no está definida. Copia .env.example a .env "
            "y arranca la BD con 'docker compose up -d'."
        )
    return dsn


def _price_eq(a: Optional[float], b: Optional[float]) -> bool:
    """Compara dos precios con tolerancia a None y a 2 decimales."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return round(float(a), 2) == round(float(b), 2)


_UPSERT_PRODUCT = """
INSERT INTO products (id, name, supermarket, category, master_category_id,
                      price, price_per_unit, unit, brand, url, image_url, source_metadata, last_seen)
VALUES (%(id)s, %(name)s, %(supermarket)s, %(category)s, %(master_category_id)s,
        %(price)s, %(price_per_unit)s, %(unit)s, %(brand)s, %(url)s, %(image_url)s, %(source_metadata)s, now())
ON CONFLICT (id) DO UPDATE SET
    name               = EXCLUDED.name,
    supermarket        = EXCLUDED.supermarket,
    category           = EXCLUDED.category,
    master_category_id = EXCLUDED.master_category_id,
    price              = EXCLUDED.price,
    price_per_unit     = EXCLUDED.price_per_unit,
    unit               = EXCLUDED.unit,
    brand              = EXCLUDED.brand,
    url                = EXCLUDED.url,
    image_url          = EXCLUDED.image_url,
    source_metadata    = EXCLUDED.source_metadata,
    last_seen          = now();
"""

_INSERT_HISTORY = """
INSERT INTO price_history (product_id, price, price_per_unit, source_metadata)
VALUES (%(id)s, %(price)s, %(price_per_unit)s, %(source_metadata)s);
"""

_UPSERT_CATEGORY = """
INSERT INTO categories (market, external_id, name, parent_name, master_category_id)
VALUES (%(market)s, %(external_id)s, %(name)s, %(parent_name)s, %(master_category_id)s)
ON CONFLICT (market, external_id) DO UPDATE SET
    name               = EXCLUDED.name,
    parent_name        = EXCLUDED.parent_name,
    master_category_id = EXCLUDED.master_category_id;
"""


def upsert_products(products: List["NormalizedProduct"]) -> Dict[str, int]:
    """
    Inserta o actualiza productos y registra cambios de precio.

    Returns:
        Estadísticas: total, new, price_changed, unchanged.
    """
    # Deduplica por id: un producto puede aparecer en varias subcategorías
    # dentro del mismo scrape. Nos quedamos con la última aparición.
    deduped: Dict[str, "NormalizedProduct"] = {}
    for p in products:
        if p and p.id:
            deduped[p.id] = p
    products = list(deduped.values())

    stats = {"total": len(products), "new": 0, "price_changed": 0, "context_changed": 0, "unchanged": 0}
    if not products:
        return stats

    with psycopg.connect(get_dsn()) as conn:
        with conn.cursor() as cur:
            ids = [p.id for p in products]
            cur.execute("SELECT id, price, source_metadata->>'price_context' FROM products WHERE id = ANY(%s)", (ids,))
            existing = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            upsert_rows = []
            history_rows = []
            for p in products:
                upsert_rows.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "supermarket": p.supermarket,
                        "category": p.category,
                        "master_category_id": p.master_category_id,
                        "price": p.price,
                        "price_per_unit": p.price_per_unit,
                        "unit": p.unit,
                        "brand": p.brand,
                        "url": p.url,
                        "image_url": p.image_url,
                        "source_metadata": Jsonb(p.source_metadata),
                    }
                )
                hist = {
                    "id": p.id,
                    "price": p.price,
                    "price_per_unit": p.price_per_unit,
                    "source_metadata": Jsonb(p.source_metadata),
                }
                if p.id not in existing:
                    stats["new"] += 1
                    history_rows.append(hist)
                elif existing[p.id][1] != p.source_metadata.get("price_context"):
                    # Nuevo baseline del ámbito; no se considera variación de precio.
                    stats["context_changed"] += 1
                    history_rows.append(hist)
                elif not _price_eq(existing[p.id][0], p.price):
                    stats["price_changed"] += 1
                    history_rows.append(hist)
                else:
                    stats["unchanged"] += 1

            # Productos primero (satisface la FK del histórico en la misma transacción).
            cur.executemany(_UPSERT_PRODUCT, upsert_rows)
            if history_rows:
                cur.executemany(_INSERT_HISTORY, history_rows)
        conn.commit()

    return stats


def upsert_categories(rows: List[Dict[str, Optional[str]]]) -> int:
    """Inserta o actualiza categorías. Devuelve el número procesado."""
    rows = [r for r in rows if r.get("external_id")]
    if not rows:
        return 0
    with psycopg.connect(get_dsn()) as conn:
        with conn.cursor() as cur:
            cur.executemany(_UPSERT_CATEGORY, rows)
        conn.commit()
    return len(rows)
