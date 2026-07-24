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

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_model() -> TextEmbedding:
    """Carga (una sola vez) el modelo de embeddings."""
    logger.info("Cargando modelo de embeddings: %s", MODEL_NAME)
    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: List[str]) -> List[np.ndarray]:
    """Devuelve un embedding (np.ndarray de dim 384) por cada texto."""
    if not texts:
        return []
    return list(get_model().embed(texts))
