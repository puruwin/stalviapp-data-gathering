"""
Scraper de Dia para obtener productos y enviarlos a Firebase.

- Obtiene el árbol de categorías desde https://www.dia.es/api/v1/common-aggregator/menu-data
- Descarga productos de cada subcategoría.
- Envía los datos a Firebase Functions (ingestProducts); solo se escriben cambios y se guarda historial de precios.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

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

# Firebase Functions - ingestProducts
FIREBASE_INGEST_URL = os.environ.get(
    "FIREBASE_INGEST_URL",
    "https://ingestproducts-yuggencccq-uc.a.run.app",
)

# Modo de prueba - limita categorías y productos para testing rápido
TEST_MODE = False  # Cambiar a False para scrapeo completo
MAX_CATEGORIES = 5  # Solo aplica si TEST_MODE = True
MAX_PRODUCTS_PER_CATEGORY = 3  # Solo aplica si TEST_MODE = True


def enviar_a_firebase(productos: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Envía los productos a Firebase Functions (ingestProducts).
    La función compara con datos existentes y solo escribe cambios; guarda historial de precios.

    Args:
        productos: Lista de diccionarios con los datos de cada producto.

    Returns:
        Respuesta JSON con ok, count, new, updated, unchanged; o None si falla.
    """
    if not FIREBASE_INGEST_URL:
        print("[!] FIREBASE_INGEST_URL no configurado.")
        return None
    if not productos:
        print("[!] No hay productos para enviar.")
        return None
    try:
        response = requests.post(
            FIREBASE_INGEST_URL,
            json={"products": productos},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        print(
            f"[OK] Firebase: {data.get('count', 0)} enviados | "
            f"nuevos: {data.get('new', 0)} | "
            f"precio cambiado: {data.get('updated', 0)} | "
            f"sin cambios: {data.get('unchanged', 0)}"
        )
        return data
    except requests.RequestException as exc:
        print(f"[X] Error al enviar a Firebase: {exc}")
        return None


def obtener_categorias() -> List[Dict[str, Any]]:
    try:
        print(f"Llamando a la API de categorías: {CATEGORIES_URL}")
        response = requests.get(CATEGORIES_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"[X] Error al obtener categorías: {exc}")
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
    print(f"[OK] Total de subcategorías obtenidas: {len(categorias)}")
    return categorias



def descargar_productos(link: str) -> Optional[List[Dict[str, Any]]]:
    url = f"{PLP_BASE_URL}{link}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("plp_items", [])
    except requests.RequestException as exc:
        print(f"[X] Error al obtener productos desde {url}: {exc}")
        return None


def procesar_producto(
    item: Dict[str, Any], categoria_info: Dict[str, str]
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
    
    # Extraer datos adicionales de la API
    product_id_api = item.get("id") or item.get("product_id") or item.get("sku")
    product_url = item.get("url") or item.get("link") or ""
    image_url = item.get("image") or item.get("image_url") or ""
    
    # Construir URL completa si es relativa
    if product_url and not product_url.startswith("http"):
        product_url = f"https://www.dia.es{product_url}"
    if image_url and not image_url.startswith("http"):
        image_url = f"https://www.dia.es{image_url}"

    # Generar ID único para Firebase (market + id de la API o hash del nombre)
    unique_id = f"{MARKET}_{product_id_api}" if product_id_api else f"{MARKET}_{hash(display_name)}"
    
    # Retornar datos en formato compatible con Firebase
    return {
        "id": unique_id,
        "name": display_name,
        "supermarket": MARKET,
        "category_path": f"{categoria_info['parent_name']} > {categoria_info['name']}",
        "price": price,
        "price_per_unit": price_per_unit,
        "unit": measure_unit,
        "brand": brand,
        "url": product_url,
        "image_url": image_url,
    }


def procesar_categoria(categoria: Dict[str, Any]) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Procesa una categoría y sus productos.
    
    Returns:
        Tupla con (éxito, mensaje, lista_de_productos)
    """
    name = categoria["name"]
    link = categoria["link"]

    # Omitir productos para categorías que empiecen con "Todo "
    if name.startswith("Todo "):
        return True, "Categoría " + name + " omitida (sin productos)", []

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
        producto_data = procesar_producto(item, categoria)
        if producto_data:
            productos_procesados.append(producto_data)

    return True, f"{len(productos_procesados)} productos procesados", productos_procesados


def main():
    inicio = datetime.now()
    print("Iniciando scraper de Dia...")

    categorias = obtener_categorias()
    if not categorias:
        print("No hay categorías para procesar.")
        return

    # Limitar categorías en modo de prueba
    if TEST_MODE:
        categorias = categorias[:MAX_CATEGORIES]
        print(f"\n[!] MODO DE PRUEBA: Limitado a {MAX_CATEGORIES} categorías y {MAX_PRODUCTS_PER_CATEGORY} productos por categoría\n")

    total = len(categorias)
    procesadas = 0
    fallidas: List[str] = []
    todos_los_productos: List[Dict[str, Any]] = []

    print(f"\nSe procesarán {total} subcategorías.\n")
    for idx, categoria in enumerate(categorias, start=1):
        print(f"[{idx}/{total}] {categoria['parent_name']} > {categoria['name']}")
        exito, mensaje, productos = procesar_categoria(categoria)
        if exito:
            procesadas += 1
            print(f"  [OK] {mensaje}")
            todos_los_productos.extend(productos)
        else:
            fallidas.append(
                f"{categoria['parent_name']} > {categoria['name']} ({mensaje})"
            )
            print(f"  [X] {mensaje}")

        time.sleep(DELAY_SECONDS)
    
    total_productos = len(todos_los_productos)

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print("\nResumen:")
    print(f"  [OK] Categorías procesadas: {procesadas}")
    print(f"  [OK] Total productos: {total_productos}")
    print(f"  [X] Categorías con error: {len(fallidas)}")
    if fallidas:
        print("  Detalle de errores:")
        for entry in fallidas:
            print(f"   - {entry}")

    print(f"\nEnviando {total_productos} productos a Firebase...")
    enviar_a_firebase(todos_los_productos)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Proceso interrumpido por el usuario")
