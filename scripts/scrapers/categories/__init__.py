"""
Módulo de gestión de categorías y taxonomía maestra.

Proporciona mapeo entre categorías de supermercados y taxonomía normalizada.
"""

from .taxonomy import MasterTaxonomy, MasterCategory
from .mapper import CategoryMapper

__all__ = ["MasterTaxonomy", "MasterCategory", "CategoryMapper"]
