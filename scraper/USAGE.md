# Uso de la aplicación de scraping

CLI unificado para scrapear supermercados (DIA, Mercadona), normalizar categorías y enviar productos a Firebase.

---

## Requisitos

- Python 3.8+
- Dependencias: `pip install -r requirements.txt` (desde `scripts/`)

## Ejecución

Desde el directorio **scripts**:

```bash
cd scripts
python main.py <comando> [opciones]
```

---

## Comandos

### 1. Scrapear productos

```bash
python main.py scrape <supermercado> [opciones]
```

**Supermercados:** `dia`, `mercadona` (Mercadona aún en desarrollo).

| Opción | Descripción |
|--------|-------------|
| `--test` | Modo test: 5 categorías, 3 productos por categoría |
| `--categories N` | Límite de categorías a procesar |
| `--products N` | Límite de productos por categoría |
| `--dry-run` | No envía datos a Firebase (solo scrapea y valida) |
| `-v`, `--verbose` | Log más detallado |

**Ejemplos:**

```bash
# Scrape completo de DIA (envía a Firebase)
python main.py scrape dia

# Prueba rápida sin enviar
python main.py scrape dia --test --dry-run

# Solo 2 categorías, 10 productos por categoría
python main.py scrape dia --categories 2 --products 10

# Scrape sin enviar a Firebase
python main.py scrape dia --dry-run
```

Tras el scrape se muestran: categorías procesadas, productos válidos, estadísticas de mapeos (confirmados/auto/pendientes) y envío a Firebase (salvo en `--dry-run`).

---

### 2. Gestión de categorías

Las categorías de cada supermercado se mapean a una **taxonomía maestra** para comparar precios entre cadenas. Los mapeos se guardan en `scrapers/data/mappings/<super>.json`.

#### Ver categorías pendientes de mapeo

```bash
python main.py categories pending <dia|mercadona>
```

Muestra categorías del supermercado que aún no tienen categoría maestra asignada (o están en estado `pending`).

#### Estadísticas de mapeos

```bash
python main.py categories stats <dia|mercadona>
```

Muestra conteo por estado: confirmados, automáticos, pendientes, rechazados.

#### Mapear una categoría manualmente

```bash
python main.py categories map <dia|mercadona> <source_id> <master_id>
```

- `source_id`: ID de la categoría del supermercado (ej. `112` en DIA).
- `master_id`: ID de la categoría maestra (ej. `aceites.aceites`).

Ejemplo:

```bash
python main.py categories map dia 112 aceites.aceites
```

#### Ver taxonomía maestra

```bash
python main.py categories taxonomy
```

Lista las categorías raíz y sus hijas de la taxonomía maestra (definida en `scrapers/data/master_taxonomy.json`).

---

## Variables de entorno

| Variable | Descripción | Por defecto |
|----------|-------------|-------------|
| `FIREBASE_INGEST_URL` | URL del endpoint de ingestión de productos | `https://ingestproducts-yuggencccq-uc.a.run.app` |

Para usar otra URL de Firebase:

```bash
set FIREBASE_INGEST_URL=https://tu-url.run.app
python main.py scrape dia
```

(Linux/macOS: `export FIREBASE_INGEST_URL=...`)

---

## Flujo típico

1. **Primera vez (DIA)**  
   `python main.py scrape dia --test --dry-run` para comprobar que todo va bien.

2. **Scrape completo**  
   `python main.py scrape dia` (envía productos a Firebase).

3. **Revisar mapeos**  
   `python main.py categories stats dia` y, si hay pendientes, `python main.py categories pending dia`.

4. **Corregir mapeos**  
   `python main.py categories map dia <source_id> <master_id>` para las categorías que quieras ajustar.

5. **Consultar taxonomía**  
   `python main.py categories taxonomy` para ver IDs maestros al mapear.

---

## Datos locales

- **Taxonomía maestra:** `scrapers/data/master_taxonomy.json`
- **Mapeos por super:** `scrapers/data/mappings/dia.json`, `mercadona.json`
- **Categorías crudas (referencia):** `scrapers/data/raw_cats/dia.json`, `mercadona.json`

Los productos normalizados incluyen `category_path` (original del super) y `master_category_id` (taxonomía común) para comparativas entre supermercados.
