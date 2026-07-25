"""
Pipeline de embeddings y catalogación.

- embed_products: calcula embeddings de productos (incremental).
- build_prototypes: prototipo por categoría maestra (híbrido centroide/texto).
- classify_pending: cataloga por kNN los productos sin categoría (cola de revisión
  si no superan el umbral de confianza).
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np

from scrapers.categories.taxonomy import get_taxonomy

from .model import embed_documents
from .store import category_text, connect, product_text, to_numpy

logger = logging.getLogger(__name__)

# Umbral de confianza (coseno) para aceptar una asignación por kNN.
# Elegido con el barrido de evaluación (embeddings/eval.py) sobre 4.4k productos
# de Mercadona (230 clases hoja): a 0.70 -> cobertura ~0.79, accuracy hoja ~0.57
# (categoría raíz bastante mayor). Es un fallback conservador: lo que no llega al
# umbral queda en cola de revisión (catalog_status='pending'). Ajustable por CLI.
DEFAULT_THRESHOLD = 0.70

# Nº mínimo de productos catalogados para usar centroide en vez de texto.
MIN_SAMPLES = 5


def embed_products(only_missing: bool = True, batch: int = 256) -> int:
    """Calcula y guarda embeddings de productos. Devuelve cuántos procesó."""
    with connect() as conn, conn.cursor() as cur:
        sql = "SELECT id, name, brand FROM products"
        if only_missing:
            sql += " WHERE embedding IS NULL"
        cur.execute(sql)
        rows = cur.fetchall()

    total = len(rows)
    logger.info("Productos a embeber: %d", total)
    for i in range(0, total, batch):
        chunk = rows[i : i + batch]
        vecs = embed_documents([product_text(name, brand) for _, name, brand in chunk])
        with connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "UPDATE products SET embedding = %s WHERE id = %s",
                [(vec, pid) for (pid, _, _), vec in zip(chunk, vecs)],
            )
            conn.commit()
        logger.info("  embebidos %d/%d", min(i + batch, total), total)
    return total


def build_prototypes(min_samples: int = MIN_SAMPLES) -> Dict[str, int]:
    """
    Construye un prototipo por categoría maestra:
      - centroide de los productos catalogados si hay >= min_samples,
      - si no, embedding del texto (ruta + keywords) de la categoría.
    Cubre todas las hojas de la taxonomía y cualquier categoría ya usada.
    """
    taxonomy = get_taxonomy()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT master_category_id, count(*)
            FROM products
            WHERE embedding IS NOT NULL AND master_category_id IS NOT NULL
            GROUP BY master_category_id
            """
        )
        counts = {r[0]: r[1] for r in cur.fetchall()}

        target_ids = set(counts) | {c.id for c in taxonomy.get_all()}
        proto_rows = []
        text_ids = []
        for mid in target_ids:
            if counts.get(mid, 0) >= min_samples:
                cur.execute(
                    "SELECT embedding FROM products "
                    "WHERE master_category_id = %s AND embedding IS NOT NULL",
                    (mid,),
                )
                vecs = [to_numpy(r[0]) for r in cur.fetchall()]
                centroid = np.mean(np.vstack(vecs), axis=0)
                proto_rows.append((mid, centroid, "centroid", len(vecs)))
            else:
                text_ids.append(mid)

        if text_ids:
            tvecs = embed_documents([category_text(mid) for mid in text_ids])
            for mid, v in zip(text_ids, tvecs):
                proto_rows.append((mid, v, "text", 0))

        cur.executemany(
            """
            INSERT INTO category_prototypes (master_category_id, embedding, source, n_samples, updated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (master_category_id) DO UPDATE SET
                embedding  = EXCLUDED.embedding,
                source     = EXCLUDED.source,
                n_samples  = EXCLUDED.n_samples,
                updated_at = now()
            """,
            proto_rows,
        )
        conn.commit()

    stats = {
        "total": len(proto_rows),
        "centroid": sum(1 for r in proto_rows if r[2] == "centroid"),
        "text": sum(1 for r in proto_rows if r[2] == "text"),
    }
    logger.info("Prototipos: %s", stats)
    return stats


_NEAREST_SQL = """
SELECT p.id, k.master_category_id, 1 - (k.embedding <=> p.embedding) AS sim
FROM products p
CROSS JOIN LATERAL (
    SELECT master_category_id, embedding
    FROM category_prototypes cp
    ORDER BY cp.embedding <=> p.embedding
    LIMIT 1
) k
WHERE p.embedding IS NOT NULL AND p.master_category_id IS NULL
"""


def classify_pending(threshold: float = DEFAULT_THRESHOLD) -> Dict[str, int]:
    """
    Cataloga por kNN los productos sin categoría maestra. Los que superan el
    umbral se asignan (catalog_status='knn'); el resto quedan en revisión
    (catalog_status='pending'). Marca como 'inference' los ya catalogados.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE products SET catalog_status = 'inference' "
            "WHERE master_category_id IS NOT NULL AND catalog_status IS NULL"
        )
        cur.execute(_NEAREST_SQL)
        rows = cur.fetchall()

        assigned = []
        pending = []
        for pid, best, sim in rows:
            if sim is not None and sim >= threshold:
                assigned.append((best, float(sim), pid))
            else:
                pending.append((float(sim) if sim is not None else None, pid))

        cur.executemany(
            "UPDATE products SET master_category_id = %s, catalog_status = 'knn', "
            "catalog_confidence = %s WHERE id = %s",
            assigned,
        )
        cur.executemany(
            "UPDATE products SET catalog_status = 'pending', catalog_confidence = %s "
            "WHERE id = %s",
            pending,
        )
        conn.commit()

    stats = {"candidatos": len(rows), "asignados_knn": len(assigned), "pendientes": len(pending)}
    logger.info("Catalogación kNN: %s", stats)
    return stats
