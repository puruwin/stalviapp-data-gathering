"""
Gestión de la taxonomía maestra de categorías.

Carga, busca y gestiona la jerarquía de categorías canónicas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Ruta al archivo de taxonomía
DATA_DIR = Path(__file__).parent.parent / "data"
TAXONOMY_FILE = DATA_DIR / "master_taxonomy.json"


@dataclass
class MasterCategory:
    """Categoría de la taxonomía maestra."""

    id: str
    name: str
    keywords: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    children: List["MasterCategory"] = field(default_factory=list)

    @property
    def level(self) -> int:
        """Nivel en la jerarquía (0 = raíz)."""
        return self.id.count(".")

    @property
    def is_leaf(self) -> bool:
        """True si no tiene hijos."""
        return len(self.children) == 0

    def all_keywords(self) -> List[str]:
        """Todas las keywords incluyendo el nombre normalizado."""
        name_normalized = self.name.lower()
        return [name_normalized] + [k.lower() for k in self.keywords]


class MasterTaxonomy:
    """Gestiona la taxonomía maestra de categorías."""

    def __init__(self, taxonomy_file: Optional[Path] = None):
        """
        Inicializa la taxonomía.

        Args:
            taxonomy_file: Ruta al archivo JSON. Si no se proporciona,
                          usa la ruta por defecto.
        """
        self.taxonomy_file = taxonomy_file or TAXONOMY_FILE
        self._categories: Dict[str, MasterCategory] = {}
        self._root_categories: List[MasterCategory] = []
        self._loaded = False

    def load(self) -> None:
        """Carga la taxonomía desde el archivo JSON."""
        if self._loaded:
            return

        logger.info(f"Cargando taxonomía desde {self.taxonomy_file}")

        try:
            with open(self.taxonomy_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Archivo de taxonomía no encontrado: {self.taxonomy_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear taxonomía: {e}")
            raise

        # Parsear categorías
        for cat_data in data.get("categories", []):
            category = self._parse_category(cat_data)
            self._root_categories.append(category)
            self._register_category(category)

        self._loaded = True
        logger.info(f"Taxonomía cargada: {len(self._categories)} categorías")

    def _parse_category(
        self,
        data: dict,
        parent_id: Optional[str] = None,
    ) -> MasterCategory:
        """Parsea una categoría del JSON."""
        category = MasterCategory(
            id=data["id"],
            name=data["name"],
            keywords=data.get("keywords", []),
            parent_id=parent_id,
        )

        # Parsear hijos recursivamente
        for child_data in data.get("children", []):
            child = self._parse_category(child_data, parent_id=category.id)
            category.children.append(child)

        return category

    def _register_category(self, category: MasterCategory) -> None:
        """Registra una categoría y sus hijos en el índice."""
        self._categories[category.id] = category
        for child in category.children:
            self._register_category(child)

    def get(self, category_id: str) -> Optional[MasterCategory]:
        """Obtiene una categoría por ID."""
        self._ensure_loaded()
        return self._categories.get(category_id)

    def get_all(self) -> List[MasterCategory]:
        """Obtiene todas las categorías."""
        self._ensure_loaded()
        return list(self._categories.values())

    def get_roots(self) -> List[MasterCategory]:
        """Obtiene las categorías raíz (nivel 0)."""
        self._ensure_loaded()
        return self._root_categories

    def get_leaves(self) -> List[MasterCategory]:
        """Obtiene las categorías hoja (sin hijos)."""
        self._ensure_loaded()
        return [c for c in self._categories.values() if c.is_leaf]

    def get_parent(self, category_id: str) -> Optional[MasterCategory]:
        """Obtiene la categoría padre."""
        category = self.get(category_id)
        if category and category.parent_id:
            return self.get(category.parent_id)
        return None

    def get_path(self, category_id: str) -> str:
        """Obtiene el path completo de una categoría (ej: 'Lácteos > Leche')."""
        category = self.get(category_id)
        if not category:
            return ""

        parts = [category.name]
        parent = self.get_parent(category_id)
        while parent:
            parts.insert(0, parent.name)
            parent = self.get_parent(parent.id)

        return " > ".join(parts)

    def search(self, query: str, limit: int = 5) -> List[MasterCategory]:
        """
        Busca categorías por nombre o keywords.

        Args:
            query: Texto a buscar.
            limit: Máximo de resultados.

        Returns:
            Lista de categorías ordenadas por relevancia.
        """
        self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for category in self._categories.values():
            score = self._match_score(query_lower, category)
            if score > 0:
                results.append((category, score))

        # Ordenar por score descendente
        results.sort(key=lambda x: x[1], reverse=True)
        return [cat for cat, _ in results[:limit]]

    def _match_score(self, query: str, category: MasterCategory) -> float:
        """Calcula score de coincidencia entre query y categoría."""
        score = 0.0

        # Match exacto en nombre
        if query == category.name.lower():
            return 1.0

        # Match parcial en nombre
        if query in category.name.lower():
            score = max(score, 0.8)

        # Match en keywords
        for keyword in category.all_keywords():
            if query == keyword:
                score = max(score, 0.9)
            elif query in keyword or keyword in query:
                score = max(score, 0.6)

        return score

    def _ensure_loaded(self) -> None:
        """Asegura que la taxonomía esté cargada."""
        if not self._loaded:
            self.load()


# Instancia global (singleton)
_taxonomy: Optional[MasterTaxonomy] = None


def get_taxonomy() -> MasterTaxonomy:
    """Obtiene la instancia global de taxonomía."""
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = MasterTaxonomy()
        _taxonomy.load()
    return _taxonomy
