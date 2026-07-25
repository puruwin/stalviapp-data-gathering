"""
Wrapper del modelo de embeddings (fastembed / ONNX, sin PyTorch).

Modelo: paraphrase-multilingual-MiniLM-L12-v2 (dim 384, multilingüe).
Se eligió por ser ligero (~0.22 GB), reproducible en CPU y cubrir español.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384

# Prefijos estilo e5 ("query:" / "passage:"). Aunque este es un modelo de
# paráfrasis (no un e5 nativo), anteponer el prefijo rompe el efecto "hub" que
# sufren los strings cortos y desnudos: sin él, consultas de una sola palabra
# ("leche") caían cerca de nombres cortos capitalizados no relacionados
# ("Brócoli", "Setas"). La búsqueda es ASIMÉTRICA: la consulta usa QUERY_PREFIX
# y los documentos (productos, textos de categoría) usan PASSAGE_PREFIX.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_model() -> TextEmbedding:
    """Carga (una sola vez) el modelo de embeddings."""
    logger.info("Cargando modelo de embeddings: %s", MODEL_NAME)
    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: List[str]) -> List[np.ndarray]:
    """Embeddings crudos (sin prefijo). Primitiva de bajo nivel."""
    if not texts:
        return []
    return list(get_model().embed(texts))


def embed_documents(texts: List[str]) -> List[np.ndarray]:
    """Embeddings de documentos/pasajes (productos, categorías) con PASSAGE_PREFIX."""
    return embed_texts([f"{PASSAGE_PREFIX}{t}" for t in texts])


def embed_query(text: str) -> np.ndarray:
    """Embedding de una consulta de búsqueda con QUERY_PREFIX."""
    return embed_texts([f"{QUERY_PREFIX}{text}"])[0]
