"""Búsqueda semántica de productos por similitud de embeddings."""

from __future__ import annotations

from typing import List, Tuple

from .model import embed_texts
from .store import connect

_SEARCH_SQL = """
SELECT id, name, price, unit, master_category_id, 1 - (embedding <=> %s) AS sim
FROM products
WHERE embedding IS NOT NULL
ORDER BY embedding <=> %s
LIMIT %s
"""


def search_products(query: str, k: int = 10) -> List[Tuple]:
    """
    Devuelve los k productos más parecidos a la consulta.

    Returns:
        Lista de tuplas (id, name, price, unit, master_category_id, similitud).
    """
    qvec = embed_texts([query])[0]
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_SEARCH_SQL, (qvec, qvec, k))
        return cur.fetchall()
