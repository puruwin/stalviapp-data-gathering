"""
Acceso a Postgres para embeddings (con registro del tipo vector de pgvector)
y utilidades para construir los textos que se embeben.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from db import get_dsn
from scrapers.categories.taxonomy import get_taxonomy


def connect() -> psycopg.Connection:
    """Abre una conexión con el tipo vector registrado."""
    conn = psycopg.connect(get_dsn())
    register_vector(conn)
    return conn


def to_numpy(v) -> np.ndarray:
    """Convierte a np.float32 un embedding devuelto por la BD (Vector, lista...)."""
    if isinstance(v, np.ndarray):
        return v.astype(np.float32)
    if hasattr(v, "to_numpy"):
        return v.to_numpy().astype(np.float32)
    return np.asarray(v, dtype=np.float32)


def product_text(name: str, brand: Optional[str] = None) -> str:
    """Texto a embeber para un producto (nombre y, si hay, marca)."""
    return f"{name} {brand}".strip() if brand else name


def category_text(master_category_id: str) -> str:
    """
    Texto representativo de una categoría maestra: su ruta jerárquica
    más sus keywords. Usado como prototipo cuando no hay productos suficientes.
    """
    taxonomy = get_taxonomy()
    cat = taxonomy.get(master_category_id)
    if not cat:
        return master_category_id.replace(".", " ")
    path = taxonomy.get_path(master_category_id)
    keywords = " ".join(cat.keywords)
    return f"{path} {keywords}".strip()
