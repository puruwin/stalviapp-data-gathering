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
from .catalogue import _source  # noqa: E402



def search_products(user_id: str, query: str, k: int = 20, province: str = '') -> List[dict]:
    """Devuelve los k productos más parecidos a la query (catálogo público)."""
    qvec = embed_query(query)
    literal = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with app_conn(user_id) as conn, conn.cursor() as cur:
        source, params, _ = _source(province)
        # Los productos sin vector siguen disponibles mediante búsqueda textual.
        # La puntuación de texto asegura que las nuevas referencias no desaparezcan.
        cur.execute(f"""SELECT p.id,p.name,p.supermarket,p.price,p.price_per_unit,p.unit,p.brand,p.image_url,
            p.master_category_id,CASE WHEN p.embedding IS NOT NULL THEN 1-(p.embedding <=> %s) ELSE 0 END AS similarity
            FROM {source}
            WHERE p.embedding IS NOT NULL OR p.name ILIKE %s
            ORDER BY (p.name ILIKE %s) DESC,similarity DESC,p.id LIMIT %s""",
            [qvec,*params,'%'+literal+'%',
             '%'+literal+'%',k])
        rows = cur.fetchall()
    for r in rows:
        # Serializa numéricos a float para JSON limpio.
        for key in ("price", "price_per_unit", "similarity"):
            if r.get(key) is not None:
                r[key] = float(r[key])
    return rows
