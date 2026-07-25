"""
Búsqueda semántica de productos para el API.

Reutiliza el modelo de embeddings del scraper (F2) para embeber la query en
Python — el front NO puede calcular el embedding en JS. Aquí se añade a la SQL
de F2 los campos que la UI necesita (imagen, marca, precio/unidad).
"""

from __future__ import annotations

import os
import sys
from typing import List

# El modelo de embeddings vive en el paquete del scraper. Lo añadimos al path
# para reutilizar embed_texts sin duplicar el wrapper de fastembed.
_SCRAPER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scraper")
if _SCRAPER_DIR not in sys.path:
    sys.path.insert(0, _SCRAPER_DIR)

from embeddings.model import embed_query  # noqa: E402

from .db import app_conn  # noqa: E402

_SEARCH_SQL = """
SELECT id, name, price, price_per_unit, unit, brand, image_url,
       master_category_id, 1 - (embedding <=> %s) AS similarity
FROM products
WHERE embedding IS NOT NULL
ORDER BY embedding <=> %s
LIMIT %s
"""


def search_products(user_id: str, query: str, k: int = 20) -> List[dict]:
    """Devuelve los k productos más parecidos a la query (catálogo público)."""
    qvec = embed_query(query)
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute(_SEARCH_SQL, (qvec, qvec, k))
        rows = cur.fetchall()
    for r in rows:
        # Serializa numéricos a float para JSON limpio.
        for key in ("price", "price_per_unit", "similarity"):
            if r.get(key) is not None:
                r[key] = float(r[key])
    return rows
