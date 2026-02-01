"""
Mapeo de categorías de supermercados a taxonomía maestra.

Proporciona inferencia automática y gestión de mapeos manuales.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models import Category
from .taxonomy import MasterCategory, MasterTaxonomy, get_taxonomy

logger = logging.getLogger(__name__)

# Ruta a los archivos de mapeo
DATA_DIR = Path(__file__).parent.parent / "data"
MAPPINGS_DIR = DATA_DIR / "mappings"


@dataclass
class CategoryMapping:
    """Mapeo de una categoría de supermercado a la taxonomía maestra."""

    source_id: str
    source_path: str
    master_id: Optional[str] = None
    status: str = "pending"  # pending, auto, confirmed, rejected
    confidence: Optional[float] = None
    suggestions: List[str] = field(default_factory=list)
    reviewed_at: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convierte a diccionario para JSON."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class CategoryMapper:
    """
    Mapea categorías de un supermercado a la taxonomía maestra.

    Combina mapeos manuales (confirmados) con inferencia automática.
    """

    # Umbral de confianza para auto-mapeo
    AUTO_CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        market: str,
        taxonomy: Optional[MasterTaxonomy] = None,
    ):
        """
        Inicializa el mapper para un supermercado.

        Args:
            market: Nombre del supermercado (dia, mercadona, etc.)
            taxonomy: Taxonomía a usar. Si no se proporciona, usa la global.
        """
        self.market = market
        self.taxonomy = taxonomy or get_taxonomy()
        self._mappings: Dict[str, CategoryMapping] = {}
        self._mappings_file = MAPPINGS_DIR / f"{market}.json"
        self._dirty = False  # True si hay cambios sin guardar
        self._load_mappings()

    def _load_mappings(self) -> None:
        """Carga los mapeos desde el archivo JSON."""
        if not self._mappings_file.exists():
            logger.warning(f"Archivo de mapeos no encontrado: {self._mappings_file}")
            return

        try:
            with open(self._mappings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear mapeos: {e}")
            return

        for mapping_data in data.get("mappings", []):
            mapping = CategoryMapping(
                source_id=mapping_data["source_id"],
                source_path=mapping_data["source_path"],
                master_id=mapping_data.get("master_id"),
                status=mapping_data.get("status", "pending"),
                confidence=mapping_data.get("confidence"),
                suggestions=mapping_data.get("suggestions", []),
                reviewed_at=mapping_data.get("reviewed_at"),
                notes=mapping_data.get("notes"),
            )
            self._mappings[mapping.source_id] = mapping

        logger.info(f"Mapeos cargados para {self.market}: {len(self._mappings)}")

    def save_mappings(self) -> None:
        """Guarda los mapeos al archivo JSON."""
        if not self._dirty:
            return

        MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "market": self.market,
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "mappings": [m.to_dict() for m in self._mappings.values()],
        }

        with open(self._mappings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._dirty = False
        logger.info(f"Mapeos guardados: {self._mappings_file}")

    def get_master_category(
        self,
        category: Category,
        auto_map: bool = True,
    ) -> Optional[str]:
        """
        Obtiene la categoría maestra para una categoría del supermercado.

        Args:
            category: Categoría del supermercado.
            auto_map: Si True, intenta inferir automáticamente si no hay mapeo.

        Returns:
            ID de la categoría maestra o None si no se puede mapear.
        """
        # Buscar mapeo existente
        mapping = self._mappings.get(category.id)

        if mapping:
            if mapping.status in ("confirmed", "auto"):
                return mapping.master_id
            elif mapping.status == "rejected":
                return None

        # Intentar inferencia automática
        if auto_map:
            return self._infer_and_save(category)

        return None

    def _infer_and_save(self, category: Category) -> Optional[str]:
        """Infiere la categoría maestra y guarda el mapeo."""
        master_id, confidence, suggestions = self._infer_category(category)

        if master_id and confidence >= self.AUTO_CONFIDENCE_THRESHOLD:
            # Auto-mapeo con alta confianza
            self._save_mapping(
                category,
                master_id=master_id,
                status="auto",
                confidence=confidence,
                suggestions=suggestions,
            )
            logger.info(
                f"Auto-mapeado: {category} -> {master_id} (confianza: {confidence:.2f})"
            )
            return master_id
        else:
            # Guardar como pending con sugerencias
            self._save_mapping(
                category,
                master_id=None,
                status="pending",
                confidence=confidence,
                suggestions=suggestions,
            )
            logger.debug(f"Categoría pendiente de mapeo: {category}")
            return None

    def _infer_category(
        self,
        category: Category,
    ) -> tuple[Optional[str], float, List[str]]:
        """
        Infiere la categoría maestra usando similitud de texto.

        Returns:
            Tupla (master_id, confidence, suggestions).
        """
        # Normalizar texto de la categoría
        source_text = self._normalize_text(f"{category.parent_name} {category.name}")
        source_words = set(source_text.split())

        best_match: Optional[MasterCategory] = None
        best_score = 0.0
        suggestions: List[tuple[str, float]] = []

        # Buscar en todas las categorías de la taxonomía
        for master_cat in self.taxonomy.get_all():
            score = self._calculate_similarity(source_words, source_text, master_cat)

            if score > 0.3:  # Umbral mínimo para sugerencias
                suggestions.append((master_cat.id, score))

            if score > best_score:
                best_score = score
                best_match = master_cat

        # Ordenar sugerencias por score
        suggestions.sort(key=lambda x: x[1], reverse=True)
        suggestion_ids = [s[0] for s in suggestions[:5]]

        if best_match:
            return best_match.id, best_score, suggestion_ids
        return None, 0.0, suggestion_ids

    def _calculate_similarity(
        self,
        source_words: set,
        source_text: str,
        master_cat: MasterCategory,
    ) -> float:
        """Calcula similitud entre categoría origen y maestra."""
        score = 0.0

        # Keywords de la categoría maestra
        master_keywords = set(
            self._normalize_text(k) for k in master_cat.all_keywords()
        )

        # Intersección de palabras
        common_words = source_words & master_keywords
        if common_words:
            score = len(common_words) / max(len(source_words), len(master_keywords))

        # Bonus por match de nombre exacto
        master_name_normalized = self._normalize_text(master_cat.name)
        if master_name_normalized in source_text:
            score = max(score, 0.8)

        # Bonus por match de keyword exacto
        for keyword in master_keywords:
            if keyword in source_text and len(keyword) > 3:
                score = max(score, 0.7)

        return score

    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para comparación."""
        # Convertir a minúsculas
        text = text.lower()

        # Eliminar acentos
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))

        # Eliminar caracteres especiales
        text = re.sub(r"[^a-z0-9\s]", " ", text)

        # Normalizar espacios
        text = " ".join(text.split())

        return text

    def _save_mapping(
        self,
        category: Category,
        master_id: Optional[str],
        status: str,
        confidence: Optional[float] = None,
        suggestions: Optional[List[str]] = None,
    ) -> None:
        """Guarda un mapeo."""
        mapping = CategoryMapping(
            source_id=category.id,
            source_path=str(category),
            master_id=master_id,
            status=status,
            confidence=confidence,
            suggestions=suggestions or [],
        )
        self._mappings[category.id] = mapping
        self._dirty = True

    def set_mapping(
        self,
        source_id: str,
        master_id: str,
        status: str = "confirmed",
        notes: Optional[str] = None,
    ) -> bool:
        """
        Establece un mapeo manualmente.

        Args:
            source_id: ID de la categoría del supermercado.
            master_id: ID de la categoría maestra.
            status: Estado del mapeo (confirmed, rejected).
            notes: Notas adicionales.

        Returns:
            True si se guardó correctamente.
        """
        if source_id not in self._mappings:
            logger.warning(f"Categoría no encontrada: {source_id}")
            return False

        # Verificar que la categoría maestra existe
        if master_id and not self.taxonomy.get(master_id):
            logger.warning(f"Categoría maestra no encontrada: {master_id}")
            return False

        mapping = self._mappings[source_id]
        mapping.master_id = master_id
        mapping.status = status
        mapping.reviewed_at = datetime.now().isoformat()
        mapping.notes = notes
        self._dirty = True

        logger.info(f"Mapeo confirmado: {mapping.source_path} -> {master_id}")
        return True

    def get_pending(self) -> List[CategoryMapping]:
        """Obtiene los mapeos pendientes de revisión."""
        return [m for m in self._mappings.values() if m.status == "pending"]

    def get_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas de mapeos."""
        stats = {"pending": 0, "auto": 0, "confirmed": 0, "rejected": 0}
        for mapping in self._mappings.values():
            stats[mapping.status] = stats.get(mapping.status, 0) + 1
        return stats
