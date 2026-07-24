"""
Arnés de evaluación de la catalogación por embeddings.

Usa los productos ya catalogados (por inferencia de keyword) como ground truth:
divide en train/test, construye prototipos con el train (híbrido) y predice el
test por kNN. Reporta accuracy top-1 y un barrido de umbral (cobertura vs
accuracy) para elegir el punto de operación.
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np

from scrapers.categories.taxonomy import get_taxonomy

from .model import embed_texts
from .store import category_text, connect, to_numpy

logger = logging.getLogger(__name__)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def evaluate(test_frac: float = 0.2, min_samples: int = 5, seed: int = 42) -> Dict:
    """Evalúa la catalogación por kNN con hold-out. Devuelve métricas."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT master_category_id, embedding FROM products "
            "WHERE embedding IS NOT NULL AND master_category_id IS NOT NULL"
        )
        rows = cur.fetchall()

    if len(rows) < 10:
        logger.warning("Muy pocos productos catalogados con embedding (%d).", len(rows))
        return {}

    labels = np.array([r[0] for r in rows])
    X = np.vstack([to_numpy(r[1]) for r in rows])

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows))
    n_test = max(1, int(len(rows) * test_frac))
    test_idx, train_idx = idx[:n_test], idx[n_test:]
    Xtr, ytr = X[train_idx], labels[train_idx]
    Xte, yte = X[test_idx], labels[test_idx]

    # Prototipos desde el train (híbrido). Cubrimos todas las etiquetas posibles.
    taxonomy = get_taxonomy()
    all_labels = sorted(
        set(ytr.tolist()) | set(yte.tolist()) | {c.id for c in taxonomy.get_leaves()}
    )
    proto_vecs, proto_labels, text_needed = [], [], []
    for lab in all_labels:
        mask = ytr == lab
        if int(mask.sum()) >= min_samples:
            proto_vecs.append(Xtr[mask].mean(axis=0))
            proto_labels.append(lab)
        else:
            text_needed.append(lab)
    if text_needed:
        for lab, v in zip(text_needed, embed_texts([category_text(l) for l in text_needed])):
            proto_vecs.append(np.asarray(v, dtype=np.float32))
            proto_labels.append(lab)

    P = _normalize(np.vstack(proto_vecs))
    proto_labels = np.array(proto_labels)
    T = _normalize(Xte)
    sims = T @ P.T
    best = sims.argmax(axis=1)
    pred = proto_labels[best]
    conf = sims.max(axis=1)
    correct = pred == yte
    acc = float(correct.mean())

    # Métricas más informativas: top-3 (hoja) y acierto a nivel de categoría raíz.
    top3_idx = np.argsort(-sims, axis=1)[:, :3]
    top3 = proto_labels[top3_idx]
    acc_top3 = float(np.mean([yte[i] in top3[i] for i in range(len(yte))]))
    root = np.array([p.split(".")[0] for p in pred])
    root_true = np.array([p.split(".")[0] for p in yte])
    acc_root = float((root == root_true).mean())

    logger.info(
        "Evaluación kNN — train=%d, test=%d, clases=%d", len(ytr), len(yte), len(all_labels)
    )
    logger.info(
        "  accuracy: hoja top-1=%.3f, hoja top-3=%.3f, categoría raíz=%.3f",
        acc, acc_top3, acc_root,
    )
    logger.info("Barrido de umbral (confianza -> cobertura / accuracy sobre cubiertos):")
    sweep = {}
    for t in (0.3, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8):
        covered = conf >= t
        cov = float(covered.mean())
        acc_c = float(correct[covered].mean()) if bool(covered.any()) else 0.0
        sweep[t] = {"cobertura": cov, "accuracy": acc_c, "n": int(covered.sum())}
        logger.info("  umbral %.2f -> cobertura %.2f, accuracy %.3f (n=%d)", t, cov, acc_c, int(covered.sum()))

    return {
        "train": len(ytr),
        "test": len(yte),
        "top1_accuracy": acc,
        "top3_accuracy": acc_top3,
        "root_accuracy": acc_root,
        "sweep": sweep,
    }
