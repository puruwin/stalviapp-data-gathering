import requests
import database


def obtener_productos_dia(url, category_id):
    """
    Llama a la API de Dia y guarda los productos en la base de datos.
    
    Args:
        url (str): URL de la API de Dia
        category_id (int): ID de la categoría en la base de datos
    
    Returns:
        int: Número de productos procesados exitosamente, None si hay error
    """
    try:
        # Hacer la petición GET a la API
        print(f"Llamando a la API: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Lanza una excepción si hay un error HTTP
        
        # Obtener los datos JSON de la respuesta
        datos = response.json()
        
        # Extraer solo el array plp_items con los campos solicitados
        plp_items = datos.get('plp_items', [])
        productos_procesados = 0
        
        for item in plp_items:
            display_name = item.get('display_name')
            price = item.get('prices', {}).get('price')
            price_per_unit = item.get('prices', {}).get('price_per_unit')
            measure_unit = item.get('prices', {}).get('measure_unit')
            brand = item.get('brand') if 'brand' in item else None
            
            # Guardar en la base de datos
            product_id = database.insert_or_update_product(
                display_name=display_name,
                price=price,
                price_per_unit=price_per_unit,
                measure_unit=measure_unit,
                category_id=category_id,
                brand=brand
            )
            
            if product_id:
                productos_procesados += 1
        
        print(f"✓ Total de productos procesados: {productos_procesados}")
        
        return productos_procesados
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Error al hacer la petición: {e}")
        return None
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return None


def obtener_categorias(url):
    """
    Llama a la API de Dia Categories y guarda todas las subcategorías en la base de datos.
    
    Args:
        url (str): URL de la API de menu-data
    
    Returns:
        list: Lista de subcategorías con id (de BD), nombre, link, categoría padre y external_id
    """
    try:
        # Hacer la petición GET a la API
        print(f"Llamando a la API: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Obtener los datos JSON
        datos = response.json()
        
        # La respuesta tiene un array 'categories'
        categorias_principales = datos.get('categories', [])
        
        if not categorias_principales:
            print(f"⚠ No se encontraron categorías en la respuesta")
            print(f"Claves disponibles: {list(datos.keys())}")
            return []
        
        # Extraer todos los children de cada categoría principal y guardarlos en BD
        subcategorias = []
        for categoria_principal in categorias_principales:
            nombre_padre = categoria_principal.get('name', 'Sin nombre')
            children = categoria_principal.get('children', [])
            
            for child in children:
                external_id = str(child.get('id', ''))
                name = child.get('name', '')
                link = child.get('link', '')
                
                # Solo procesar subcategorías que tengan nombre y link
                if name and link:
                    # Guardar en la base de datos
                    category_id = database.insert_or_update_category(
                        external_id=external_id,
                        name=name,
                        link=link,
                        parent_category=nombre_padre
                    )
                    
                    if category_id:
                        subcat_info = {
                            'id': category_id,  # ID de la base de datos
                            'external_id': external_id,  # ID de la API
                            'name': name,
                            'link': link,
                            'parent_category': nombre_padre
                        }
                        subcategorias.append(subcat_info)
        
        print(f"✓ Total de subcategorías guardadas: {len(subcategorias)}")
        return subcategorias
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Error al hacer la petición: {e}")
        return []
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    try:
        # Inicializar la base de datos
        print("Inicializando base de datos...")
        if not database.init_database():
            print("✗ Error al inicializar la base de datos. Verifica la conexión y el esquema.")
            exit(1)
        
        # URL de la API de Dia para categorías
        categories_url = "https://www.dia.es/api/v1/common-aggregator/menu-data"

        # Obtener las subcategorías (children) y guardarlas en BD
        subcategorias = obtener_categorias(categories_url)
        
        if not subcategorias:
            print("✗ No se pudieron obtener las categorías. Revisa los logs anteriores.")
        else:
            print(f"\n{'='*60}")
            print(f"Procesando {len(subcategorias)} subcategorías...")
            print(f"{'='*60}\n")
            
            productos_totales = 0
            
            # Obtener productos de cada subcategoría
            for i, subcat in enumerate(subcategorias, 1):
                print(f"\n[{i}/{len(subcategorias)}] {subcat['parent_category']} > {subcat['name']}")
                
                if not subcat.get('link'):
                    print(f"  ⚠ Subcategoría sin link, saltando...")
                    continue
                
                # Usar el ID de la base de datos (no el external_id)
                category_id = subcat['id']
                api_url = f"https://www.dia.es/api/v1/plp-back/reduced{subcat['link']}"
                
                resultado = obtener_productos_dia(api_url, category_id)
                if resultado is not None:
                    productos_totales += resultado
                    print(f"  ✓ {resultado} productos procesados")
                else:
                    print(f"  ✗ Error al obtener productos")
            
            print(f"\n{'='*60}")
            print(f"✓ Proceso completado")
            print(f"✓ Total de productos procesados: {productos_totales}")
            print(f"{'='*60}")
    
    except KeyboardInterrupt:
        print("\n\n⚠ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n✗ Error crítico: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cerrar la conexión a la base de datos
        database.close_connection()
