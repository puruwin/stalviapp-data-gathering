#!/usr/bin/env python3
"""
CLI de embeddings y catalogación (F2).

Uso (desde la raíz del repo):
    python scraper/embed.py products      # calcula embeddings de productos (incremental)
    python scraper/embed.py prototypes    # construye prototipos de categoría
    python scraper/embed.py classify       # cataloga por kNN los productos sin categoría
    python scraper/embed.py eval           # evalúa la catalogación (hold-out + barrido)
    python scraper/embed.py search "leche desnatada"   # búsqueda semántica
    python scraper/embed.py all            # products + prototypes + classify
"""

from __future__ import annotations

import argparse
import logging

from embeddings.eval import evaluate
from embeddings.pipeline import (
    DEFAULT_THRESHOLD,
    build_prototypes,
    classify_pending,
    embed_products,
)
from embeddings.search import search_products

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embeddings y catalogación")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prod = sub.add_parser("products", help="Calcular embeddings de productos")
    p_prod.add_argument("--all", action="store_true", help="Recalcular todos (no solo los que faltan)")

    sub.add_parser("prototypes", help="Construir prototipos de categoría")

    p_cls = sub.add_parser("classify", help="Catalogar por kNN los productos sin categoría")
    p_cls.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)

    sub.add_parser("eval", help="Evaluar la catalogación (hold-out)")

    p_search = sub.add_parser("search", help="Búsqueda semántica")
    p_search.add_argument("query", help="Texto a buscar")
    p_search.add_argument("-k", type=int, default=10)

    p_all = sub.add_parser("all", help="products + prototypes + classify")
    p_all.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)

    args = parser.parse_args()

    if args.command == "products":
        n = embed_products(only_missing=not args.all)
        logger.info("Embeddings calculados: %d", n)
    elif args.command == "prototypes":
        build_prototypes()
    elif args.command == "classify":
        classify_pending(threshold=args.threshold)
    elif args.command == "eval":
        evaluate()
    elif args.command == "search":
        for pid, name, price, unit, mcat, sim in search_products(args.query, k=args.k):
            price_s = f"{price:.2f}€" if price is not None else "s/precio"
            print(f"  {sim:.3f}  {name}  ({price_s}, {mcat})")
    elif args.command == "all":
        embed_products(only_missing=True)
        build_prototypes()
        classify_pending(threshold=args.threshold)


if __name__ == "__main__":
    main()
