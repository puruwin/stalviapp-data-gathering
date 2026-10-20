# Catálogo y disponibilidad por provincia

Un producto tiene una sola fila `products`, con clave cadena + SKU de origen.
`product_availability` relaciona esa ficha con los centros donde se observó y
guarda precio, unidad, disponibilidad y fecha por zona. Dos cadenas que venden el
mismo EAN conservan sus ofertas separadas; los embeddings no deduplican artículos.

## Recopilar y actualizar

Aplicar primero `db/migrations/0006_regional_catalogue.sql` (o `bash db/migrate.sh`).

```bash
# Usar una carpeta nueva por fecha. Una carpeta existente reanuda esa captura;
# no vuelve a descargar los checkpoints ya completos.
.venv/bin/python scraper/main.py scrape mercadona --all-zones \
  --checkpoint-dir scraper/runs/mercadona-2026-10-20 --workers 4
.venv/bin/python scraper/main.py scrape consum --all-zones \
  --checkpoint-dir scraper/runs/consum-2026-10-20 --workers 4

# Ampliar el descubrimiento de Mercadona con un fichero de CP peninsulares.
.venv/bin/python scraper/mercadona_catalogue.py scraper/runs/mercadona-extra \
  --postal-codes-file /ruta/codigos-postales.txt
.venv/bin/python scraper/regional_catalogue.py mercadona scraper/runs/mercadona-extra

# Incorporar a las tablas regionales una captura completa de Consum ya existente.
.venv/bin/python scraper/regional_catalogue.py consum scraper/runs/consum-2026-10-20
```

Mercadona resuelve el almacén mediante la respuesta oficial al introducir un CP
(`x-customer-wh` y `x-customer-pc`). Se recorren todas las categorías de cada
almacén distinto. La muestra predeterminada cubre capitales peninsulares y CP de
varios municipios de Alicante: **no es un censo exhaustivo de centros logísticos**.
Un CP sin cobertura no se reemplaza por el almacén predeterminado. Las respuestas
y asignaciones quedan en `discovery.json` y los catálogos comprimidos por almacén.

Consum usa el listado público de centros y su provincia y dirección publicadas.
La zona anónima `0` nunca se atribuye a una provincia.

Solo se importa una captura cuando sus zonas y categorías han terminado. La
importación de disponibilidad de cada cadena es transaccional: retira de las zonas
incluidas los productos que ya no aparecen, conserva otras zonas y añade histórico
solo si cambia su precio o precio por unidad. Reimportar es idempotente. Un
checkpoint antiguo no puede sustituir un cierre de zona más reciente.

## Consultar

Los endpoints de catálogo, ficha, histórico y búsqueda admiten `province=03` para
Alicante (prefijo provincial de dos dígitos). Sin provincia conservan el catálogo
global y su precio de referencia. Con provincia:

- Solo aparecen productos observados en al menos una zona asociada a ella.
- Una ficha aparece una vez aunque la tengan varios centros.
- Se elige un centro de forma estable por `zone_id`; no se presenta su precio como
  mínimo, promedio ni precio uniforme de toda la provincia.
- Precio, fecha, variación e histórico corresponden al mismo centro elegido.
- Una ficha sin observación provincial devuelve 404; no se rellena con otra zona.
- El resumen y los contadores de categorías usan esa misma provincia.

La app ofrece el selector en el backoffice y en la búsqueda de productos. Se
comparte entre pantallas y se guarda por cuenta en ese dispositivo. Las pestañas
permiten acceder a todas las categorías del ámbito elegido.

## Límites

La inclusión provincial significa presencia en alguna zona de esa provincia,
no reparto a cada dirección ni stock en tiempo real. Los CP comprobados y el tipo
de evidencia se guardan en `catalogue_zone_provinces`. Una provincia desconocida
devuelve catálogo vacío. El catálogo online no representa todo el surtido físico.

La selección de provincia filtra catálogo y búsqueda; las listas de compra ya
existentes y sus totales siguen usando el precio global de referencia de `products`.
No se cambia silenciosamente el contenido ni el precio de esas listas al filtrar.

Los artículos sin embedding siguen siendo accesibles por nombre en `/search`;
calcular sus vectores y unificar la taxonomía son procesos independientes.

## Corrección del precio de Mercadona

`unit_price` de la API es el precio del envase y `reference_price` (o `bulk_price`
como alternativa) es el precio por kg/l/unidad de referencia. El adaptador anterior
los intercambiaba. Las capturas nuevas usan el esquema `unit-price-v2`; su contexto
no compara esos precios corregidos con los baselines anteriores de otro esquema.
La captura del 20 de octubre se reparó desde las respuestas originales, con copia
previa y actualizando sus propios baselines sin registrar variaciones ficticias.
Las referencias antiguas que no reaparecieron se conservan en la base y en las
listas; carecen de disponibilidad provincial comprobada y quedan fuera del filtro.
