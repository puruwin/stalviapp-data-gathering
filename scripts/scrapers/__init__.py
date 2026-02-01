"""
Módulo de scrapers para supermercados.

Cada supermercado tiene su propio submódulo que implementa BaseScraper.
"""

from .base import BaseScraper
from .models import Category, RawProduct, NormalizedProduct
from .validators import validate_product, validate_products
from .ingest import ingest_products, ingest_products_batch

__all__ = [
    "BaseScraper",
    "Category",
    "RawProduct",
    "NormalizedProduct",
    "validate_product",
    "validate_products",
    "ingest_products",
    "ingest_products_batch",
]
