# Documentación de scrapers

Este documento describe cómo funciona cada scraper del proyecto: la arquitectura común, los modelos de datos y las particularidades de DIA, Mercadona, Carrefour y Consum.

---

## 1. Arquitectura común

Todos los scrapers extienden **BaseScraper** (`scrapers/base.py`) y comparten el mismo flujo de datos.

### 1.1 Contrato (métodos que cada scraper implementa)

| Método | Descripción |
|--------|-------------|
| **get_categories()** | Obtiene la lista de categorías del supermercado. Resultado cacheado en memoria. |
| **scrape_plp(category)** | Descarga los productos de una categoría (PLP = Product Listing Page). Devuelve lista de `RawProduct`. |
| **normalize(raw_product, category)** | Convierte un producto crudo al formato común `NormalizedProduct`. Devuelve `None` si el producto no es válido. |

Opcional (todos lanzan `NotImplementedError` por ahora):

- **scrape_pdp(product_url)**: enriquecimiento desde página de detalle (PDP). No implementado en ninguno.

### 1.2 Flujo compartido (BaseScraper)

- **scrape_category(category)**: llama a `scrape_plp(category)` y luego normaliza cada producto con `normalize()`. Devuelve `List[NormalizedProduct]`.
- **scrape_all(max_categories, max_products_per_category)**: obtiene categorías, recorre cada una con `scrape_category()`, aplica `http.delay()` entre categorías. Usado por el CLI para ejecutar un scrape completo.

### 1.3 Modelos de datos comunes

**Category** (`scrapers/models.py`)

- `id`: identificador de la categoría en el supermercado (string).
- `name`: nombre de la categoría.
- `parent_name`: nombre de la categoría padre (ej. "Supermercado", "Aceite, especias y salsas").
- `link`: ruta o identificador usado para construir la URL del PLP (depende de cada API).

**RawProduct**

- `raw_id`: ID del producto en la API (string).
- `raw_data`: diccionario con los datos crudos del producto tal como los devuelve la API.

**NormalizedProduct** (contrato de salida para Firebase)

- `id`: `"{market}_{product_id}"` (único entre supermercados).
- `name`, `supermarket`, `category` (texto tipo "Padre > Hijo").
- `master_category_id`: categoría de la taxonomía maestra (vía CategoryMapper).
- `price`, `price_per_unit`, `unit`, `brand`, `url`, `image_url`.

### 1.4 CategoryMapper y mapeos

- Cada scraper tiene un **CategoryMapper(market)** que asigna categorías del supermercado a la taxonomía maestra (`scrapers/data/master_taxonomy.json`).
- Los mapeos se guardan en `scrapers/data/mappings/{market}.json` (confirmados, automáticos o pendientes).
- **save_category_mappings()**: persiste los mapeos en disco. Lo llama el CLI después del scrape.

### 1.5 Cliente HTTP

- Por defecto se usa **HttpClient** (`scrapers/http_client.py`): `requests.Session`, retry ante 429/5xx, cache opcional, `delay()` entre peticiones.
- Carrefour puede usar **CurlCffiClient** (`scrapers/http_client_curl_cffi.py`) si está instalado `curl_cffi`, para imitar TLS de Chrome y reducir 403 por fingerprint (JA3).

---

## 2. Scraper DIA

### 2.1 APIs

| Recurso | URL | Respuesta |
|---------|-----|-----------|
| Categorías | `GET https://www.dia.es/api/v1/common-aggregator/menu-data` | JSON con `categories[]` (cada una con `name`, `children[]`). |
| Productos (PLP) | `GET https://www.dia.es/api/v1/plp-back/reduced{category.link}` | JSON con `plp_items[]`. |

### 2.2 Categorías

- Estructura: `data["categories"]` → cada elemento tiene `name` (padre) y `children[]`.
- Cada hijo tiene `id`, `name`, `link`.
- Se omiten categorías cuyo nombre empieza por "Todo " (agregadores).
- Se construye `Category(id, name, parent_name, link)`; `link` es la ruta relativa que se concatena al `PLP_BASE_URL`.

### 2.3 Productos (PLP)

- Una sola petición por categoría: `PLP_BASE_URL + category.link`.
- Los productos están en `data["plp_items"]`.
- ID del producto: `item["id"]` o `item["product_id"]` o `item["sku"]`; fallback hash del `display_name`.

### 2.4 Normalización

- Nombre: `display_name`.
- Precios: `item["prices"]["price"]`, `price_per_unit`, `measure_unit`.
- Marca: `item["brand"]`.
- URL e imagen: `url`/`link`, `image`/`image_url`.

### 2.5 Particularidades

- API sencilla; no requiere headers especiales ni cookies.
- Estructura plana: un nivel de categorías padre y sus hijos; un PLP por categoría con lista directa de productos.

---

## 3. Scraper Mercadona

### 3.1 APIs

| Recurso | URL | Respuesta |
|---------|-----|-----------|
| Categorías | `GET https://tienda.mercadona.es/api/categories/?lang=es&wh=alc1` | JSON con `results[]` (cada uno con `id`, `name`, `categories[]`). |
| Productos (PLP) | `GET https://tienda.mercadona.es/api/categories/{category_id}/?lang=es&wh=alc1` | JSON del detalle de categoría: `categories[]` (subcategorías), cada una con `products[]`. |

### 3.2 Categorías

- Estructura: `data["results"]` → cada elemento es un grupo padre con `id`, `name` y `categories[]` (hijas).
- Solo se incluyen hijas con `published=True`.
- Cada categoría hoja tiene `id`, `name`. No hay `link` en la API; se usa `link = str(id)` para construir la URL del detalle.

### 3.3 Productos (PLP)

- Una petición por categoría: `CATEGORY_DETAIL_URL` con `category.id`.
- La respuesta es el detalle de la categoría: tiene `categories[]` (subcategorías, ej. "Aceite de oliva"), y cada subcategoría tiene `products[]`.
- Se recorren todas las subcategorías y se concatenan todos los `products[]` en una sola lista de `RawProduct`.

### 3.4 Normalización

- Nombre: `display_name`.
- Precios: `price_instructions["bulk_price"]`, `unit_price` o `reference_price`; unidad en `reference_format` o `size_format`. Valores en string; se convierten a float.
- Marca: la API no expone marca; se deja `brand=None`.
- URL e imagen: `share_url`, `thumbnail`.

### 3.5 Particularidades

- Dos niveles en categorías (grupo padre → categorías hijas) y en PLP (categoría → subcategorías con productos).
- Parámetros fijos en URLs: `lang=es`, `wh=alc1`.
- Mapeos de categorías ya definidos en `scrapers/data/mappings/mercadona.json`.

---

## 4. Scraper Carrefour

### 4.1 APIs

| Recurso | URL | Respuesta |
|---------|-----|-----------|
| Categorías (menú) | `GET https://www.carrefour.es/cloud-api/categories-api/v1/categories/menu?sale_point=005290&depth=1&current_category=foodRootCategory&limit=3&lang=es&freelink=true` | JSON con `menu[]` → `menu[0].childs[0]` = sección Supermercado; sus `childs[]` son las categorías hoja. |
| Productos (PLP) | `GET https://www.carrefour.es/cloud-api/plp-food-analytics/v1/{category.link}` | JSON con campo **`impressions`** que es un **string** con un array JSON dentro. |

### 4.2 Categorías

- Estructura anidada: `data["menu"][0]["childs"][0]` es la sección "Supermercado" (nombre desde `name` o `analytics.title`).
- Las categorías útiles son `parent["childs"]`: cada una tiene `id` (ej. `"cat20006"`), `name`, `url_rel` (ej. `"/supermercado/bebe/cat20006/c"`).
- Se acepta `result` como envoltorio: `data = data.get("result", data)`.
- `Category.link` se guarda como `url_rel` sin barra inicial para concatenar al `PLP_BASE_URL`.

### 4.3 Productos (PLP)

- Una petición por categoría: `PLP_BASE_URL + "/" + category.link`.
- La respuesta tiene **`impressions`**: puede ser un **string** (array JSON) o ya un array. Si es string, se hace `json.loads(impressions)` para obtener la lista de ítems.
- Cada ítem tiene `item_id`, `item_name` (slug con guiones), `price`, `item_brand`, etc. No hay `url` ni imagen en el payload de analytics.

### 4.4 Normalización

- Nombre: **no** viene como texto legible; viene `item_name` en formato slug (ej. `"toallitas-para-bebe-fresh-my-carrefour-baby-80-ud"`). Se convierte con **`_slug_to_display_name()`**: reemplazar guiones por espacios y aplicar `.title()`.
- Precio: `item["price"]` (numérico). No hay precio por unidad ni unidad en el payload → `price_per_unit=None`, `unit=None`.
- Marca: `item["item_brand"]`.
- URL e imagen: no vienen en analytics → `url=""`, `image_url=""`.

### 4.5 Particularidades

- **Parse y formato del PLP**: el campo `impressions` debe leerse como string y parsearse con `json.loads()` (o usarse como lista si ya viene parseado). Los nombres de producto se formatean desde slug a texto legible.
- **403 por WAF/fingerprint TLS**: Carrefour puede devolver 403 a clientes con fingerprint TLS distinto al de un navegador (ej. Python `requests`). Para evitarlo:
  1. **curl_cffi**: si está instalado (`pip install curl_cffi`), el scraper usa **CurlCffiClient**, que imita TLS de Chrome. Es la opción recomendada.
  2. Si no: se usan headers de navegador (User-Agent, Referer, Origin, etc.) y una visita previa a `/supermercado/` para obtener cookies (**warmup**).
  3. Opcional: variable de entorno **CARREFOUR_COOKIES** con cookies copiadas del navegador (formato `nombre=valor; nombre2=valor2`) para inyectarlas en la sesión.
- **save_category_mappings()**: igual que el resto; los mapeos se guardan en `scrapers/data/mappings/carrefour.json` (se crea en la primera ejecución si no existe).

---

## 5. Scraper Consum

### 5.1 APIs

| Recurso | URL | Respuesta |
|---------|-----|-----------|
| Categorías (menú) | `GET https://tienda.consum.es/api/rest/V1.0/shopping/category/menu` | JSON: `result` es un **array** de categorías raíz. Cada nodo tiene `id`, `name`/`nombre`, `url`, `subcategories[]` (recursivo). |
| Productos (PLP) | `GET https://tienda.consum.es/api/rest/V1.0/catalog/product?page=N&offset=0&orderById=5&showProducts=true&originProduct=undefined&showRecommendations=false&categories={category_id}` | JSON: `result` con `totalCount`, `hasMore`, `products[]`. Paginación: `page=1`, `page=2`, ... hasta `hasMore=false`. |

### 5.2 Categorías

- Estructura: árbol recursivo; cada nodo tiene `id`, `name`/`nombre`, `subcategories[]`. Las hojas tienen `subcategories: []`.
- Se usan **solo categorías hoja** (donde `subcategories` está vacío) para no duplicar productos. Recorrido recursivo con `_collect_leaf_categories(nodes, parent_name, out)`.
- Para cada hoja: `Category(id=str(cat["id"]), name=cat["name"], parent_name=padre, link=str(cat["id"]))`. El `link` es el id porque la API de productos usa `categories={id}`.
- Payload puede venir en `data.get("result", data)`; si es lista, es el árbol raíz.

### 5.3 Productos (PLP)

- URL con `categories=category.id` y `page=N`. Query fija: `orderById=5&showProducts=true&originProduct=undefined&showRecommendations=false`.
- Paginación: bucle con `page=1`, luego `page=2`, ... hasta que `result.hasMore` sea false. Concatenar todos los `result.products[]`. Aplicar `http.delay()` entre páginas.
- Cada producto tiene `id`, `productData` (name, brand, url, imageURL), `media[]`, `priceData` (prices[], unitPriceUnitType).

### 5.4 Normalización

- Nombre: `productData.name`.
- Marca: `productData.brand` → si es dict, `brand.name`, si no None.
- URL e imagen: `productData.url`, `productData.imageURL` o primer `media[0].url`.
- Precio: en `priceData.prices[]` buscar entrada con `id == "OFFER_PRICE"`; si no, usar la primera. De esa entrada, `value.centAmount` y `value.centUnitAmount`. Si el valor parece céntimos (entero ≥ 100), dividir por 100 para euros; si no, usar como euros. Unidad: `priceData.unitPriceUnitType`.

### 5.5 Particularidades

- **Árbol grande**: el menú de categorías es muy grande (muchos niveles); solo se recorren y guardan las hojas.
- **Paginación**: el PLP tiene paginación por `page`; hay que iterar hasta `hasMore=false`.
- **Headers**: el scraper usa headers por defecto (X-TOL-LOCALE, X-TOL-ZONE, X-TOL-CHANNEL, X-TOL-CURRENCY, X-TOL-SHIPPING-ZONE, X-TOL-APP, Referer) para que la API acepte las peticiones.
- **save_category_mappings()**: igual que el resto; mapeos en `scrapers/data/mappings/consum.json`.

---

## 6. Resumen comparativo

| Aspecto | DIA | Mercadona | Carrefour | Consum |
|---------|-----|-----------|-----------|--------|
| **Categorías** | `categories[]` → `children[]` | `results[]` → `categories[]` | `menu[0].childs[0].childs[]` | Árbol recursivo, solo hojas |
| **Link categoría** | `link` (ruta) | `id` (numérico) | `url_rel` (ruta) | `id` (numérico) |
| **PLP** | 1 URL → `plp_items[]` | 1 URL → detalle con `categories[].products[]` | 1 URL → `impressions` (string JSON) | Paginación `page` → `products[]` |
| **Nombre producto** | `display_name` | `display_name` | Slug → `_slug_to_display_name(item_name)` | `productData.name` |
| **Precio** | `prices.price`, etc. | `price_instructions.bulk_price`, etc. | `price` (numérico) | `priceData.prices[].value.centAmount` |
| **Marca** | `brand` | No disponible → `None` | `item_brand` | `productData.brand.name` |
| **URL / imagen** | Sí en API | `share_url`, `thumbnail` | No en analytics → vacío | `productData.url`, `imageURL` o `media[0].url` |
| **Cliente HTTP** | HttpClient | HttpClient | CurlCffiClient si hay curl_cffi | HttpClient con headers X-TOL-* |
| **Anti-403** | No necesario | No necesario | curl_cffi, warmup, CARREFOUR_COOKIES | Headers X-TOL-* por defecto |

---

## 7. Archivos de referencia

- **Base y modelos**: `scrapers/base.py`, `scrapers/models.py`
- **HTTP**: `scrapers/http_client.py`, `scrapers/http_client_curl_cffi.py`
- **Categorías**: `scrapers/categories/mapper.py`, `scrapers/categories/taxonomy.py`
- **Scrapers**: `scrapers/dia/scraper.py`, `scrapers/mercadona/scraper.py`, `scrapers/carrefour/scraper.py`, `scrapers/consum/scraper.py`
- **Mapeos**: `scrapers/data/mappings/{dia,mercadona,carrefour,consum}.json`
- **CLI**: `main.py` (comando `scrape {dia|mercadona|carrefour|consum}`)
