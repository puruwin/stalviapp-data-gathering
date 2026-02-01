"""
Modelos de datos para el sistema de scraping.

Define el contrato común que todos los scrapers deben seguir.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Category:
    """Categoría de productos del supermercado."""

    id: str
    name: str
    parent_name: str
    link: str

    def __str__(self) -> str:
        return f"{self.parent_name} > {self.name}"


@dataclass
class RawProduct:
    """
    Datos crudos de un producto tal como vienen de la API.
    
    Cada scraper extrae los datos en bruto y los almacena aquí
    antes de normalizarlos.
    """

    raw_id: str
    raw_data: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """Acceso conveniente a raw_data."""
        return self.raw_data.get(key, default)


@dataclass
class NormalizedProduct:
    """
    Producto normalizado - contrato final compatible con Firebase.
    
    Este es el formato que se envía al endpoint de ingesta.
    Todos los scrapers deben producir este formato.
    """

    id: str  # "{market}_{product_id}"
    name: str
    supermarket: str
    category: str  # Categoría original del supermercado
    master_category_id: Optional[str]  # Categoría normalizada de la taxonomía maestra
    price: Optional[float]
    price_per_unit: Optional[float]
    unit: Optional[str]
    brand: Optional[str]
    url: str
    image_url: str

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para envío a Firebase."""
        return asdict(self)

    def is_valid(self) -> bool:
        """Verifica que el producto tenga los campos mínimos requeridos."""
        return bool(self.id and self.name and self.supermarket)
