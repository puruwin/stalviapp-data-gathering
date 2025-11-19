"""
Scraper de Dia con integración al esquema de categorías normalizadas.

- Obtiene el árbol de categorías desde https://www.dia.es/api/v1/common-aggregator/menu-data
- Registra mappings mercado↔taxonomía (pending si no existe master).
- Descarga productos de cada subcategoría y los guarda en la BD.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

import database

MARKET = "dia"
CATEGORIES_URL = "https://www.dia.es/api/v1/common-aggregator/menu-data"
PLP_BASE_URL = "https://www.dia.es/api/v1/plp-back/reduced"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/118.0.4472.124 Safari/537.36"
    ),
    "Accept": "application/json",
}
DELAY_SECONDS = 1


def obtener_categorias() -> List[Dict[str, Any]]:
    try:
        print(f"Llamando a la API de categorías: {CATEGORIES_URL}")
        response = requests.get(CATEGORIES_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"✗ Error al obtener categorías: {exc}")
        return []

    categorias = []
    for categoria_principal in data.get("categories", []):
        parent_name = categoria_principal.get("name", "Sin nombre")
        for child in categoria_principal.get("children", []):
            external_id = child.get("id")
            name = child.get("name")
            link = child.get("link")
            if not external_id or not name or not link:
                continue
            categorias.append(
                {
                    "id": str(external_id),
                    "name": name,
                    "parent_name": parent_name,
                    "link": link,
                }
            )
    print(f"✓ Total de subcategorías obtenidas: {len(categorias)}")
    return categorias


def resolver_master_category(external_id: str, name: str, parent_name: str):
    mapping = database.ensure_market_category_mapping(
        market=MARKET,
        external_id=external_id,
        external_name=name,
        external_parent=parent_name,
    )
    return mapping.get("master_category_id") if mapping else None


def descargar_productos(link: str) -> Optional[List[Dict[str, Any]]]:
    url = f"{PLP_BASE_URL}{link}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("plp_items", [])
    except requests.RequestException as exc:
        print(f"✗ Error al obtener productos desde {url}: {exc}")
        return None


def procesar_producto(item: Dict[str, Any], category_db_id: int) -> Optional[int]:
    display_name = item.get("display_name")
    if not display_name:
        return None

    prices = item.get("prices", {}) or {}
    price = prices.get("price")
    price_per_unit = prices.get("price_per_unit")
    measure_unit = prices.get("measure_unit")
    brand = item.get("brand")

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
        print(f"✗ Error al registrar producto '{display_name}': {exc}")
        return None


def procesar_categoria(categoria: Dict[str, Any]) -> Tuple[bool, str]:
    external_id = categoria["id"]
    name = categoria["name"]
    parent_name = categoria["parent_name"]
    link = categoria["link"]

    master_category_id = resolver_master_category(external_id, name, parent_name)
    category_db_id = database.insert_or_update_category(
        external_id=external_id,
        name=name,
        link=link,
        parent_category=parent_name,
        market=MARKET,
        master_category_id=master_category_id,
    )
    if not category_db_id:
        return False, "No se pudo registrar la categoría en BD"

    productos = descargar_productos(link)
    if productos is None:
        return False, "Error al descargar productos"
    if not productos:
        return True, "Sin productos"

    insertados = 0
    for item in productos:
        product_id = procesar_producto(item, category_db_id)
        if product_id:
            insertados += 1

    return True, f"{insertados} productos procesados"


def main():
    print("Inicializando base de datos...")
    if not database.init_database():
        print("✗ Error al inicializar la base de datos.")
        return

    categorias = obtener_categorias()
    if not categorias:
        print("No hay categorías para procesar.")
        return

    total = len(categorias)
    procesadas = 0
    fallidas: List[str] = []
    pendientes_mapping: List[str] = []

    print(f"\nSe procesarán {total} subcategorías.\n")
    for idx, categoria in enumerate(categorias, start=1):
        print(f"[{idx}/{total}] {categoria['parent_name']} > {categoria['name']}")
        exito, mensaje = procesar_categoria(categoria)
        if exito:
            procesadas += 1
            print(f"  ✓ {mensaje}")
            mapping = database.get_market_category_mapping(MARKET, categoria["id"])
            if mapping and not mapping.get("master_category_id"):
                pendientes_mapping.append(
                    f"{categoria['parent_name']} > {categoria['name']}"
                )
        else:
            fallidas.append(
                f"{categoria['parent_name']} > {categoria['name']} ({mensaje})"
            )
            print(f"  ✗ {mensaje}")

        time.sleep(DELAY_SECONDS)

    print("\nResumen:")
    print(f"  ✓ Categorías procesadas: {procesadas}")
    print(f"  ✗ Categorías con error: {len(fallidas)}")
    if fallidas:
        print("  Detalle de errores:")
        for entry in fallidas:
            print(f"   - {entry}")

    if pendientes_mapping:
        print("\nCategorías pendientes de asignar master_category:")
        for entry in pendientes_mapping:
            print(f"   - {entry}")

    database.close_connection()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠ Proceso interrumpido por el usuario")
