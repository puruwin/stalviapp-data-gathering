"""
Scraper de Mercadona con integración a base de datos normalizada.

- Obtiene todas las categorías hijas de https://tienda.mercadona.es/api/categories/?lang=es&wh=alc1
- Para cada categoría hija descarga los productos desde /api/categories/{category_id}/?lang=es&wh=alc1
- Inserta/actualiza categorías, mapeos y productos en la base de datos.
- Opcionalmente mantiene un volcado JSON por categoría en datos_mercadona/{id}_{nombre}.json.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

import database

MARKET = "mercadona"
BASE_CATEGORIES_URL = "https://tienda.mercadona.es/api/categories/?lang=es&wh=alc1"
CATEGORY_DETAIL_URL = (
    "https://tienda.mercadona.es/api/categories/{category_id}/?lang=es&wh=alc1"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
DELAY_SECONDS = 1
SAVE_JSON = True

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "datos_mercadona"


def normalizar_nombre(nombre: str) -> str:
    normalized = nombre.strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_áéíóúñü]", "", normalized)
    return normalized


def obtener_categorias() -> List[Dict[str, Any]]:
    try:
        response = requests.get(BASE_CATEGORIES_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"✗ Error al obtener categorías: {exc}")
        return []

    categorias = []
    for categoria_padre in data.get("results", []):
        parent_name = categoria_padre.get("name", "Sin nombre")
        parent_id = categoria_padre.get("id")
        for categoria_hija in categoria_padre.get("categories", []):
            if not categoria_hija.get("published"):
                continue
            categorias.append(
                {
                    "id": categoria_hija.get("id"),
                    "name": categoria_hija.get("name", "sin_nombre"),
                    "parent_name": parent_name,
                    "parent_id": parent_id,
                }
            )
    return categorias


def obtener_productos_categoria(category_id: int) -> Dict[str, Any] | None:
    url = CATEGORY_DETAIL_URL.format(category_id=category_id)
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        print(f"✗ Error al obtener productos de la categoría {category_id}: {exc}")
        return None


def guardar_json(data: Dict[str, Any], category_id: int, category_name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{category_id}_{normalizar_nombre(category_name)}.json"
    filepath = OUTPUT_DIR / filename

    with filepath.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def resolver_master_category(category_id: int, category_name: str, parent_name: str):
    mapping = database.ensure_market_category_mapping(
        market=MARKET,
        external_id=str(category_id),
        external_name=category_name,
        external_parent=parent_name,
    )
    return mapping.get("master_category_id") if mapping else None


def procesar_producto(producto: Dict[str, Any], category_db_id: int) -> Optional[int]:
    display_name = producto.get("display_name")
    if not display_name:
        return None

    price_info = producto.get("price_instructions", {}) or {}
    price = price_info.get("unit_price") or price_info.get("bulk_price")
    price_per_unit = price_info.get("bulk_price")
    measure_unit = price_info.get("reference_format")
    brand = None
    badges = producto.get("badges", {})
    if "brand" in producto:
        brand = producto.get("brand")
    elif badges.get("brand"):
        brand = badges.get("brand")

    try:
        return database.insert_or_update_product(
            display_name=display_name,
            price=price,
            price_per_unit=price_per_unit,
            measure_unit=measure_unit,
            category_id=category_db_id,
            brand=brand,
        )
    except Exception as exc:
        print(f"✗ Error al procesar producto '{display_name}': {exc}")
        return None


def procesar_categoria(categoria: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    category_id = categoria["id"]
    category_name = categoria["name"]
    parent_name = categoria["parent_name"]

    if category_id is None:
        return False, "ID no disponible"

    data = obtener_productos_categoria(category_id)
    if data is None:
        return False, "Error al descargar productos"

    if SAVE_JSON:
        guardar_json(data, category_id, category_name)

    master_category_id = resolver_master_category(category_id, category_name, parent_name)
    category_db_id = database.insert_or_update_category(
        external_id=str(category_id),
        name=category_name,
        market=MARKET,
        parent_category=parent_name,
        master_category_id=master_category_id,
    )
    if not category_db_id:
        return False, "No se pudo registrar la categoría en BD"

    productos = []
    for cat in data.get("categories", []):
        productos.extend(cat.get("products", []))
    if not productos and "products" in data:
        productos = data.get("products", [])

    if not productos:
        return True, "Sin productos en respuesta"

    insertados = 0
    for producto in productos:
        product_id = procesar_producto(producto, category_db_id)
        if product_id:
            insertados += 1

    return True, f"{insertados} productos procesados"


def main() -> None:
    print("Inicializando base de datos...")
    if not database.init_database():
        print("✗ Error al inicializar la base de datos. Abortando.")
        return

    print("Obteniendo categorías de Mercadona...")
    categorias = obtener_categorias()

    if not categorias:
        print("No se pudieron obtener categorías. Finalizando.")
        return

    total = len(categorias)
    procesadas = 0
    fallidas: List[str] = []
    pendientes_mapping: List[str] = []

    print(f"Se procesarán {total} categorías.\n")

    for idx, categoria in enumerate(categorias, start=1):
        category_name = categoria["name"]
        parent_name = categoria["parent_name"]
        print(f"[{idx}/{total}] {parent_name} -> {category_name}")

        exito, mensaje = procesar_categoria(categoria)
        if exito:
            procesadas += 1
            print(f"  ✓ {mensaje}")
            mapping = database.get_market_category_mapping(
                MARKET, str(categoria["id"])
            )
            if mapping and not mapping.get("master_category_id"):
                pendientes_mapping.append(f"{parent_name} -> {category_name}")
        else:
            fallidas.append(f"{parent_name} -> {category_name} ({mensaje})")
            print(f"  ✗ {mensaje}")

        time.sleep(DELAY_SECONDS)

    print("\nResumen:")
    print(f"  ✓ Categorías procesadas correctamente: {procesadas}")
    print(f"  ✗ Categorías con error: {len(fallidas)}")
    if fallidas:
        print("  Lista de categorías fallidas:")
        for entry in fallidas:
            print(f"   - {entry}")

    if pendientes_mapping:
        print("\nCategorías sin master_category asignada (pending mapping):")
        for entry in pendientes_mapping:
            print(f"   - {entry}")

    database.close_connection()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario.")
