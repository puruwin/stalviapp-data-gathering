# Catálogo de Consum

Se unifica por SKU el catálogo de las zonas de reparto que Consum publica en
España. Cada artículo conserva el EAN original, su imagen, clasificación nativa,
precios, condiciones promocionales y procedencia de la observación. La cobertura
peninsular se refiere a las zonas donde Consum ofrece catálogo, no a una promesa
de reparto en todos los códigos postales de la península.

## Ejecutar

Requiere las migraciones hasta `0005_source_metadata.sql`, PostgreSQL y las
mismas dependencias del scraper existente. Desde la raíz del repositorio:

```sh
# Catálogo completo de todas las zonas reales, con fotos verificadas y persistencia.
.venv/bin/python scraper/main.py scrape consum --all-zones \
  --checkpoint-dir ./runs/consum/2026-10-20 \
  --report ./runs/consum/2026-10-20/result.json

# Para comprobarlo sin escribir productos, históricos ni mapeos, añadir --dry-run.
# Usar un directorio NUEVO para una nueva observación. Reutilizarlo solo para
# reanudar el mismo recorrido: las respuestas ya descargadas se leen de caché.
```

El recorrido admite entre una y cuatro conexiones (`--workers 1` a `4`). Dentro
cada zona las peticiones son secuenciales, con pausa y el retry del cliente común.
Los archivos de ejecución no se incorporan a Git (`/runs/` está ignorado).

Se puede trabajar por fases sobre la misma evidencia:

```sh
.venv/bin/python scraper/consum_catalogue.py discover --work-dir ./runs/consum/2026-10-20
.venv/bin/python scraper/consum_catalogue.py collect --work-dir ./runs/consum/2026-10-20
.venv/bin/python scraper/consum_catalogue.py prepare --work-dir ./runs/consum/2026-10-20
.venv/bin/python scraper/consum_catalogue.py images --work-dir ./runs/consum/2026-10-20
.venv/bin/python scraper/consum_catalogue.py import --work-dir ./runs/consum/2026-10-20
```

`prepare` bloquea la importación si queda una zona real sin terminar o fallida.
Una zona publicada que devuelve un catálogo vacío se registra como tal y se
prueban las demás rutas de reparto del mismo centro. El catálogo anónimo de
control es adicional; su fallo no se interpreta como cobertura territorial.

Continúa disponible el recorrido de categorías y el piloto inicial:

```sh
.venv/bin/python scraper/main.py scrape consum \
  --category-id 2076 --category-id 2156 --category-id 1294 --dry-run \
  --output /tmp/consum-products.json --report /tmp/consum-pilot.json
.venv/bin/python scraper/main.py scrape consum --test --dry-run
.venv/bin/python scraper/main.py categories pending consum
.venv/bin/python scraper/main.py categories map consum ID CATEGORIA_MAESTRA
```

`--all-zones` no se combina con límites de categorías/productos. Un ID de hoja
incorrecto falla antes de descargar. `--products N` limita también las peticiones.

## Cobertura y paginación

- El listado público `/api/rest/V1.0/shipping/area` proporciona los centros y sus
  rutas de reparto. Se agrupan rutas del mismo centro y se excluyen registros de
  prueba y direcciones con códigos postales inválidos.
- El catálogo por zona usa los encabezados `X-TOL-ZONE` y `X-TOL-SHIPPING-ZONE`.
  Se recorre `/api/rest/V1.0/catalog/product` sin filtro de categoría: esto incluye
  artículos que no están accesibles recorriendo solamente las hojas del menú.
- Se solicitan hasta 100 productos por página. La paginación real es `offset`;
  modificar únicamente `page` devolvía la misma página en el adaptador antiguo.
- `totalCount` cuenta filas, incluidos patrocinados que pueden repetirse. Se
  comprueba el número de filas recibidas antes de deduplicar por SKU. Páginas
  repetidas completas, respuestas inválidas, truncamientos y fallos de descarga
  se registran como error y no se convierten en ausencia de productos.
- Se conservan las respuestas comprimidas, cabeceras de zona, URL y fecha real de
  observación por página. Los checkpoints se escriben de forma atómica. Reanudar
  usa los datos guardados; un archivo incompleto se aparta y vuelve a descargar.
- Las campañas virtuales no crean categorías de producto duplicadas. El menú
  mantiene las rutas jerárquicas completas; las equivalencias maestras sin revisar
  quedan pendientes, porque la inferencia genérica confundía leche con huevos y
  detergente con té. Las categorías nativas completas se importan a PostgreSQL.

## Un artículo, un precio de referencia con procedencia

La identidad es `consum_{code}`, usando el SKU de las URL públicas. El ID interno
API y el EAN se guardan por separado; no se inventan ni corrigen códigos de barras.
Se conserva un único producto aunque aparezca en muchos centros.

El precio mostrado en el backoffice es una referencia, identificada en su ficha.
La elección es estable: se prefiere la observación anónima disponible y después
el centro de menor ID que publique el artículo. Los precios y disponibilidad de
los demás centros no sobrescriben ese precio de referencia. Las observaciones
regionales quedan en `regional-observations.json` y en las respuestas originales;
la base guarda la cobertura por centros y provincias de cada artículo.

No se presupone un precio único en toda la península. La FAQ de Consum indica
una excepción territorial para bebidas azucaradas en Cataluña. Como comprobación
del 20 de octubre de 2026, el mismo SKU 302745, EAN 5449000009067, Coca-Cola de
2 litros, devolvió `PRICE` de 2,15 € en el centro 660 de Albacete y 2,52 € en el
centro 41 de Barcelona; ambos sin ofertas asociadas. El €/l también difería.
En frescos hay que distinguir ese caso de un cambio de peso estimado de la pieza.

`price_context` identifica el ámbito del precio (`consum:online:zone-N:EUR` o
`consum:online:anonymous:zone-unspecified:EUR`). Un cambio de contexto crea un
baseline propio y se cuenta como `context_changed`, sin anunciarlo como una
variación de precio. El API compara y representa únicamente registros históricos
del mismo contexto que el producto actual. No se asigna una zona a los registros
antiguos que carecían de ella.

## Precios y promociones

- `centAmount` y `centUnitAmount` ya contienen euros, incluso para enteros mayores
  de 100: no se dividen entre 100.
- Se usa `OFFER_PRICE` solo ante una promoción vigente, inmediata, de precio
  directo para el producto, con importe coincidente. Cheques regalo, cupones y
  compras condicionadas no se descuentan del precio individual. Sin evidencia
  suficiente se conserva `PRICE`; las condiciones originales siguen disponibles.
- Las promociones se evalúan a la fecha de observación guardada, también al
  reproducir una descarga. No se reinterpreta una oferta antigua con la fecha de hoy.
- El precio por unidad usa `centUnitAmount` y su referencia, normalizada a kg, l,
  ud o lavado cuando se reconoce. Se conservan las demás unidades de origen.
- Se guarda la disponibilidad original y `temporaryOutOfStock`. Una descarga
  fallida nunca descataloga productos. No se calculan importes de carne o pescado
  multiplicando pesos supuestos.

## Imágenes

La URL principal de numerosos productos (`.../SKU.jpg`) devuelve HTTP 404 aunque
la galería sí publique fotografías (`.../SKU_001.jpg`). Se da prioridad a esa
galería, ordenada según Consum, y se conservan sus alternativas de origen.

La auditoría hace HEAD al CDN de Consum, comprueba HTTP 200 y contenido de imagen,
sin descargar ni almacenar las fotografías. Para referencias sin galería se
comprueba la ruta estándar alternativa antes de aceptarla: nunca se da por válida
una URL calculada sin verificarla. El backoffice prueba las alternativas cuando
falla una imagen y reinicia su estado al cambiar de producto o URL.

Si Consum no publica una fotografía accesible, queda `image_status=missing` y se
muestra el marcador de imagen ausente. Los fallos transitorios se distinguen de
los HTTP 404. No se generan fotografías ni se sustituyen por las de otro producto.

## Evidencia y verificación

El directorio de cada ejecución contiene:

- `zones.json`, respuestas comprimidas por centro y `collection-report.json`:
  objetivos, paginación, catálogo vacío, errores y cobertura.
- `products.json`, `categories.json` y `catalogue-report.json`: catálogo unificado
  validado antes de importar.
- `regional-observations.json`: precios normalizados observados en cada centro.
- `image-audit.json` y `image-audit-report.json`: URL elegida, comprobación HTTP,
  fecha, fotos ausentes y fallos transitorios, separados.
- `import-report.json`: altas, cambios de precio, cambios de contexto y repetidos.

Los metadatos JSONB de `products` y `price_history` conservan la observación de
referencia, EAN, SKU, ámbito, precios originales, condiciones de oferta, formato e
imágenes. Repetir el mismo precio y contexto actualiza el producto sin duplicar
el histórico. No se borran productos ausentes de una ejecución.

```sh
.venv/bin/python -m pytest scraper/tests/ api/tests/test_catalogue.py -q
cd app && npx tsc --noEmit && npx expo export --platform web
```

Las pruebas cubren la paginación, patrocinados repetidos, fallos y truncamientos,
precios y promociones, elección de imágenes, unificación por SKU, exclusión de
zonas de prueba y aislamiento del histórico por ámbito. La prueba optativa con
`TEST_DATABASE_URL` usa tablas temporales de PostgreSQL; los tests de API revierten
sus datos al terminar.

El acceso usa una API interna pública sin autenticación. No existe un contrato
público de estabilidad ni se ha configurado una ejecución periódica. El estudio
previo recoge las restricciones de `robots.txt` sobre `/api/`.

Fuentes: [catálogo](https://tienda.consum.es/),
[FAQ de precios](https://tienda.consum.es/site/es/faq),
[robots](https://tienda.consum.es/robots.txt).
