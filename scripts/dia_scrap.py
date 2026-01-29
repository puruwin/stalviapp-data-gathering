"""
Scraper de Dia con integración al esquema de categorías normalizadas.

- Obtiene el árbol de categorías desde https://www.dia.es/api/v1/common-aggregator/menu-data
- Registra mappings mercado↔taxonomía (pending si no existe master).
- Descarga productos de cada subcategoría y los guarda en la BD.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
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

# Webhook de Make - Configura tu URL aquí o usa la variable de entorno MAKE_WEBHOOK_URL
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "https://hook.eu1.make.com/eqfew5rrriwhj06qupci94goq1g6o9sv")

# Modo de prueba - limita categorías y productos para testing rápido
TEST_MODE = True  # Cambiar a False para scrapeo completo
MAX_CATEGORIES = 5  # Solo aplica si TEST_MODE = True
MAX_PRODUCTS_PER_CATEGORY = 3  # Solo aplica si TEST_MODE = True


def enviar_webhook(resultado: Dict[str, Any]) -> bool:
    """
    Envía los resultados del scrapeo al webhook de Make.
    
    Args:
        resultado: Diccionario con el resumen del scrapeo
        
    Returns:
        True si el envío fue exitoso, False en caso contrario
    """
    if not MAKE_WEBHOOK_URL:
        print("⚠ Webhook no configurado. Configura MAKE_WEBHOOK_URL para enviar resultados.")
        return False
    
    try:
        response = requests.post(
            MAKE_WEBHOOK_URL,
            json=resultado,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        print(f"✓ Resultados enviados al webhook de Make correctamente")
        return True
    except requests.RequestException as exc:
        print(f"✗ Error al enviar al webhook: {exc}")
        return False


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


def procesar_producto(
    item: Dict[str, Any], category_db_id: int, categoria_info: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Procesa un producto y retorna sus datos para el webhook.
    
    Returns:
        Diccionario con los datos del producto o None si hay error
    """
    display_name = item.get("display_name")
    if not display_name:
        return None

    prices = item.get("prices", {}) or {}
    price = prices.get("price")
    price_per_unit = prices.get("price_per_unit")
    measure_unit = prices.get("measure_unit")
    brand = item.get("brand")

    try:
        product_id = database.insert_or_update_product(
            display_name=display_name,
            price=price,
            price_per_unit=price_per_unit,
            measure_unit=measure_unit,
            category_id=category_db_id,
            brand=brand,
        )
        if product_id:
            # Retornar datos del producto para el webhook
            return {
                "id": product_id,
                "nombre": display_name,
                "precio": price,
                "precio_por_unidad": price_per_unit,
                "unidad_medida": measure_unit,
                "marca": brand,
                "categoria": categoria_info["name"],
                "categoria_padre": categoria_info["parent_name"],
                "market": MARKET,
            }
        return None
    except Exception as exc:
        print(f"✗ Error al registrar producto '{display_name}': {exc}")
        return None


def procesar_categoria(categoria: Dict[str, Any]) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Procesa una categoría y sus productos.
    
    Returns:
        Tupla con (éxito, mensaje, lista_de_productos)
    """
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
        return False, "No se pudo registrar la categoría en BD", []

    # Omitir productos para categorías que empiecen con "Todo "
    if name.startswith("Todo "):
        return True, "Categoría + " + name + " + omitida (sin productos)", []

    productos = descargar_productos(link)
    if productos is None:
        return False, "Error al descargar productos", []
    if not productos:
        return True, "Sin productos", []

    # Limitar productos en modo de prueba
    if TEST_MODE:
        productos = productos[:MAX_PRODUCTS_PER_CATEGORY]

    productos_procesados: List[Dict[str, Any]] = []
    for item in productos:
        producto_data = procesar_producto(item, category_db_id, categoria)
        if producto_data:
            productos_procesados.append(producto_data)

    return True, f"{len(productos_procesados)} productos procesados", productos_procesados


def main():
    inicio = datetime.now()
    print("Inicializando base de datos...")
    if not database.init_database():
        print("✗ Error al inicializar la base de datos.")
        return

    categorias = obtener_categorias()
    if not categorias:
        print("No hay categorías para procesar.")
        return

    # Limitar categorías en modo de prueba
    if TEST_MODE:
        categorias = categorias[:MAX_CATEGORIES]
        print(f"\n⚠ MODO DE PRUEBA: Limitado a {MAX_CATEGORIES} categorías y {MAX_PRODUCTS_PER_CATEGORY} productos por categoría\n")

    total = len(categorias)
    procesadas = 0
    fallidas: List[str] = []
    pendientes_mapping: List[str] = []
    todos_los_productos: List[Dict[str, Any]] = []

    print(f"\nSe procesarán {total} subcategorías.\n")
    for idx, categoria in enumerate(categorias, start=1):
        print(f"[{idx}/{total}] {categoria['parent_name']} > {categoria['name']}")
        exito, mensaje, productos = procesar_categoria(categoria)
        if exito:
            procesadas += 1
            print(f"  ✓ {mensaje}")
            todos_los_productos.extend(productos)
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
    
    total_productos = len(todos_los_productos)

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print("\nResumen:")
    print(f"  ✓ Categorías procesadas: {procesadas}")
    print(f"  ✓ Total productos: {total_productos}")
    print(f"  ✗ Categorías con error: {len(fallidas)}")
    if fallidas:
        print("  Detalle de errores:")
        for entry in fallidas:
            print(f"   - {entry}")

    if pendientes_mapping:
        print("\nCategorías pendientes de asignar master_category:")
        for entry in pendientes_mapping:
            print(f"   - {entry}")

    # Preparar y enviar resultados al webhook de Make
    resultado_webhook = {
        "market": MARKET,
        "timestamp": fin.isoformat(),
        "duracion_segundos": round(duracion, 2),
        "test_mode": TEST_MODE,
        "resumen": {
            "categorias_total": total,
            "categorias_procesadas": procesadas,
            "categorias_error": len(fallidas),
            "productos_total": total_productos,
            "pendientes_mapping": len(pendientes_mapping),
            "errores": fallidas[:10] if fallidas else [],
            "status": "success" if len(fallidas) == 0 else "partial" if procesadas > 0 else "failed"
        },
        "productos": todos_los_productos
    }
    
    print(f"\nEnviando {total_productos} productos al webhook...")
    enviar_webhook(resultado_webhook)

    database.close_connection()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠ Proceso interrumpido por el usuario")
