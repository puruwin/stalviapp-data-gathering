# Backoffice local

Ruta web autenticada: `/backoffice`, accesible con el botón «Abrir backoffice»
en la cabecera de «Mis listas». Usa la sesión JWT existente, el cliente HTTP de
la app y FastAPI; no depende del prototipo publicado en Sites.

## Arrancar

Desde la raíz de Stalviapp, con PostgreSQL y las dependencias habituales instaladas:

```sh
docker compose up -d
.venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

En otra terminal:

```sh
cd app
npm run web -- --host localhost
```

Entra en la aplicación, inicia sesión y abre el backoffice, o visita
`http://localhost:8081/backoffice`. No hacen falta nuevas dependencias ni migraciones.

## Datos reales

- Consultas de solo lectura como `app_user` a `products` y `price_history`.
- Listado paginado (25, 50 o 100 por página), búsqueda textual por nombre, marca
  o referencia, filtros por categoría, marca, supermercado y evolución; ordenación
  y agrupación por familia original, marca o supermercado.
- Resumen calculado sobre todo el catálogo; resultados y paginación corresponden
  a los filtros. Los contadores de los encabezados plegables describen la página.
- Ficha con imagen original, referencia interna, marca, clasificación, precio,
  precio/unidad, fechas del scraper y enlace a la fuente.
- Gráfico escalonado a 30/90/365 días: fecha real de cada cambio, precio vigente al
  inicio del intervalo y extensión solo hasta la última observación del scraper.
  No se interpolan precios ni se inventan valores cuando faltan registros.
- El precio anterior es la última observación no nula con un precio diferente al
  actual. Sin ese dato, la variación aparece como «Sin comparación», no 0 %.
- Mercadona y el catálogo unificado de Consum alimentan el catálogo. La ficha
  identifica la procedencia del precio de referencia de Consum; el histórico
  compara solamente observaciones del mismo ámbito. Las imágenes usan las
  fotografías originales verificadas y alternativas de galería. Alcance y
  trazabilidad en [consum.md](consum.md). La API no expone embeddings.

Favoritos y alertas son preferencias locales aisladas por cuenta, guardadas con
AsyncStorage. Las alertas muestran si el último precio conocido cumple el objetivo
al consultar el catálogo; no hay notificaciones ni comprobación en segundo plano.
La exportación CSV incluye solo la página visible y neutraliza fórmulas de celdas.
El catálogo sigue gestionado por el scraper: el backoffice no crea, edita ni borra
productos. Todos los usuarios autenticados pueden consultar este catálogo público;
no se ha creado un rol administrador nuevo.

El diseño completo se implementa en `BackofficeScreen.web.tsx` con CSS acotado
al backoffice. La ruta nativa conserva listado, búsqueda, ficha y registros
históricos accesibles; no se ha ejecutado una compilación iOS/Android.

## API

Todos los endpoints requieren `Authorization: Bearer …`:

- `GET /catalogue/summary`: métricas y facetas globales.
- `GET /catalogue/products`: `q`, `category`, `brand`, `supermarket`, `change`,
  `group_by`, `sort`, `page`, `page_size`, `ids` repetible (máximo 500).
- `GET /catalogue/products/{id}`: ficha o 404.
- `GET /catalogue/products/{id}/history?days=90`: intervalo, puntos y total de
  observaciones. Incluye como máximo un registro anterior al inicio del intervalo.

## Verificación

```sh
.venv/bin/python -m pytest api/tests/test_catalogue.py
cd app
npx tsc --noEmit
npx tsc --noEmit -p e2e/tsconfig.json
npx expo export --platform web
npm run test:web -- backoffice.spec.ts --project=desktop-chromium --project=mobile-chromium
```

Las pruebas del API insertan cuatro productos de prueba en una transacción,
consultan como `app_user` y hacen rollback al finalizar. Requieren pytest, httpx
y la base de desarrollo. Las pruebas web usan las cuentas efímeras y la limpieza
ya establecidas por `e2e/fixtures.ts`.

## Comprobación ejecutada (20 de octubre de 2026)

- Cuatro pruebas del API aprobadas: autenticación, validación, filtros,
  paginación, precios nulos, baseline e histórico con un solo registro.
- TypeScript de la app y de las pruebas sin errores.
- Exportación web de Expo completada, incluyendo el CSS del backoffice.
- Navegador sobre la app y API existentes en localhost: acceso desde Mis listas,
  catálogo de 4.650 productos/26 categorías, búsqueda por referencia, filtros
  (239 bajadas), agrupación por marca, favoritos, guardado de alerta y
  paginación hasta 51–100 de 4.650.
- Ficha y gráfico comprobados a 1440 × 1000 y 390 × 844; sin desbordamiento
  horizontal en la comprobación móvil. Cuenta de prueba temporal.
- Se añaden pruebas E2E para repetir el recorrido; la suite Playwright completa
  no se ha ejecutado en esta integración. El recorrido indicado se verificó
  usando el navegador. No se han compilado los proyectos nativos.
