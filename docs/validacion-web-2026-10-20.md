# Validación web de Stalvi — 20 de octubre de 2026

Validación local sobre Postgres + pgvector, FastAPI y Expo SDK 57. Navegador:
Chromium 154 mediante Playwright. No se ha desplegado ni modificado producción.

## Red y modelo

La configuración restringida contiene `huggingface.co`, `*.huggingface.co`,
`*.xethub.hf.co`, `us.aws.cdn.hf.co`, `tienda.mercadona.es`,
`prod-mercadona.imgix.net` y `docs.expo.dev`, además del preset de gestores de paquetes.
El estado de política comunicado por el servicio es `unknown`; la conectividad
descrita aquí se ha comprobado con peticiones reales a través del proxy heredado.

| Comprobación | Resultado |
| --- | --- |
| Metadatos de Hugging Face | HTTP 200 |
| Descarga ONNX | `huggingface.co` → HTTP 302 → `us.aws.cdn.hf.co` → HTTP 200 |
| Categorías de Mercadona | HTTP 200; 152 categorías procesadas, ninguna fallida |
| Imagen de Mercadona en Chromium | HTTP 200, 300 × 300 píxeles, con TLS verificado |
| Documentación de Expo v57 | HTTP 200 |

Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, servido
por `Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`, revisión
`faf4aa4225822f3bc6376869cb1164e8e3feedd0`. Dependencias observadas:
fastembed 0.9.0 y ONNX Runtime 1.31.0. Caché: `/workspace/.cache/fastembed`
(aproximadamente 241 MB). Prefijos del código: `query:` y `passage:`.

La descarga y la API se ejecutaron con `FASTEMBED_CACHE_PATH` apuntando a esa
caché. Para Chromium hubo que importar la CA pública del proxy al almacén NSS y
permitir al navegador escribir en él. No se desactivó la verificación TLS.

## Catálogo y embeddings

La base estaba vacía al comenzar. Se ejecutaron el scraper completo de Mercadona
y `python scraper/embed.py all`:

- 4.597 registros normalizados, correspondientes a **4.329 productos únicos**.
- **4.329 embeddings de 384 dimensiones**, ninguno pendiente.
- **253 prototipos**: 132 centroides y 121 basados en texto.
- Ningún candidato sin categoría en el paso de clasificación kNN.

El scraper reescribe automáticamente el JSON de mappings. Se revisó ese efecto y
se restauró el archivo versionado; los datos y vectores permanecen en Postgres.
El nuevo mapping automático detectado fue `Turrones` → `cafe.te`, lo que requiere
revisión de catalogación antes de dar por buena esa categoría.

## API y navegador

Se usaron cuentas y listas efímeras, eliminadas al terminar cada ejecución.
Se comprobó la API con dos usuarios, catálogo real y sin simular embeddings:

- Registro, login, perfil y rechazo de consultas sin token.
- Validación de búsqueda vacía y de `k` fuera de rango.
- Resultados ordenados por similitud y con precios serializados.
- Crear, consultar, renombrar y borrar listas.
- Añadir un producto y volver a añadirlo: se incrementa la cantidad sin duplicar
  el item; cambiar cantidad, marcar comprado, quitar y vaciar.
- Totales y resumen de listas coherentes con precio × cantidad.
- Aislamiento RLS: otro usuario no puede leer ni modificar la lista o sus items.
  Los DELETE que responden 204 sobre datos ajenos no eliminan los datos del dueño.

En Chromium se verificaron registro, persistencia de sesión tras recargar,
creación de lista, búsqueda de «leche», imágenes, añadir un producto, incrementar
y reducir cantidad, marcar comprado, renombrar, vaciar y borrar la lista, cerrar
sesión y volver a entrar. Para el primer resultado observado
(helado de leche merengada, 2,95 €), el total cambia de 2,95 € a 5,90 € y vuelve a
2,95 € al reducir la cantidad. Los controles anidados requirieron clicks físicos
por los defectos de accesibilidad descritos abajo.

La última ejecución completa terminó sin errores JavaScript ni peticiones
fallidas. También se comprobó el índice a 390 × 844 píxeles, sin desbordamiento
horizontal. Los menús y diálogos se probaron esperando el final de sus animaciones.

## Relevancia: validación no superada

Generar todos los vectores no basta para considerar correcta la búsqueda. Sobre
el catálogo completo se observaron estos primeros resultados:

| Consulta | Primeros resultados |
| --- | --- |
| `leche` | Helado de leche merengada; cereales rellenos de leche; leche desnatada sin lactosa |
| `leche desnatada` | Helado de leche merengada; cereales rellenos de leche; leche desnatada sin lactosa |
| `chocolate negro` | Cacahuetes con chocolate negro; chocolate negro 55 % con almendras; chocolate negro 55 % |
| `agua` | Dos eau de toilette; granizado de agua de cebada; esponja; agua destilada |
| `platano` | Queso grana padano; salsas de queso; sazonador de pasta; chorizo |
| `plátano` | Banana; petit de fresa y plátano; fruta congelada de fresa y plátano |

Las seis consultas de la última ejecución tardaron entre 20 y 40 ms con el modelo
ya cargado. Es una muestra local, no una prueba de carga.

Queda pendiente mejorar y medir la relevancia, especialmente consultas de una
palabra y variantes sin tilde. La documentación previa que considera resuelta la
relevancia de F2 no garantiza ese resultado con este catálogo y fastembed 0.9.0.

## Accesibilidad: incidencias confirmadas

- En resultados y detalle, `List.Item` envuelve controles interactivos en un
  ancestro `aria-disabled="true"`. Playwright considera deshabilitados los botones
  internos aunque sus handlers funcionan al hacer click físico. Revisar las filas
  de `app/app/(app)/search.tsx` y `app/app/(app)/list/[id].tsx`.
- La casilla con `role="checkbox"` no expone `aria-checked`. El PATCH devuelve
  `checked: true` y la UI cambia visualmente, pero el estado no se comunica a
  tecnologías de asistencia.
- Varios botones de solo icono no tienen nombre accesible (añadir producto,
  cantidades y menús). Añadir etiquetas que describan cada acción.

## Otras comprobaciones

- `python -m pytest scraper/tests/ -q`: **8 passed**.
- `cd app && npx tsc --noEmit`: correcto.
- `EXPO_NO_TELEMETRY=1 EXPO_OFFLINE=1 CI=1 npx expo export --platform web`:
  correcto; exportación generada en `/tmp/stalvi-web-export`.

El flujo funcional y la calidad de búsqueda deben evaluarse por separado: los
endpoints y los totales funcionan, pero esta validación no da por aceptadas la
relevancia ni la accesibilidad.

## Continuación: sesión, accesibilidad y regresión automatizada

Tras la validación inicial se corrigieron los defectos de accesibilidad indicados
arriba y el manejo de sesión:

- El cliente comunica los 401 autenticados al proveedor de sesión. Se eliminan
  token, usuario persistido y caché de React Query, y la guardia vuelve al login.
- Al recargar se valida el perfil con `/auth/me`. Una caída de red conserva la
  sesión y muestra el error recuperable; un token inválido se elimina.
- Al cerrar sesión o cambiar de cuenta se cancelan las consultas y se limpia la
  caché. Un 401 de un token anterior no invalida el token nuevo.
- Las filas de productos usan un contenedor informativo sin el ancestro
  deshabilitado de `List.Item`. Los campos, botones y menús tienen nombres
  accesibles y las casillas exponen `aria-checked`.
- Hay errores visibles y reintentos para listas, búsqueda, total y mutaciones.
  Borrar una lista vuelve al índice mediante `dismissTo`, sin duplicarlo.

Suite guardada en `app/e2e/`, con instrucciones en `app/e2e/README.md` y comando
`npm run test:web`. Última ejecución: **14 passed (1,1 min)**, siete casos en cada
viewport de Chromium 154: escritorio 1280 × 900 y móvil web 390 × 844 con eventos
táctiles. Se comprobaron:

1. Token guardado inválido, recarga y navegación atrás protegida.
2. HTTP 401 durante la sesión, limpieza y vuelta al login sin reintentos del token.
3. Credenciales incorrectas, caída del login y recuperación.
4. Servidor caído durante la recarga, listas, creación y búsqueda; reintentos.
5. Persistencia, navegación atrás y cambio de cuenta sin recargar el documento.
6. Respuesta 401 tardía de la cuenta anterior sin cerrar la nueva sesión.
7. Login, crear, buscar, añadir, aumentar/reducir cantidad, total, marcar comprado,
   quitar, renombrar, volver a añadir, vaciar y borrar.

El recorrido usa productos y embeddings reales; las caídas y el 401 controlado
se simulan en el tráfico del navegador. No se usan clicks forzados ni coordenadas.
Las cuentas de prueba se eliminan con sus listas después de cada caso.
TypeScript de app y pruebas y la exportación web final también pasan.

**Cobertura pendiente al cierre de esta primera continuación:** los proyectos de Firefox y WebKit están configurados,
pero no ejecutados. La descarga de sus binarios requiere permitir
`cdn.playwright.dev`, bloqueado por la política del entorno con HTTP 403
`Domain forbidden`. Chromium usa el binario que ya estaba instalado. No se ha
eludido la política ni desactivado TLS. Se pidió ampliar la lista de dominios y
queda pendiente esa configuración para completar la matriz de navegadores.

La mejora de relevancia de búsqueda y el mapping de Turrones siguen pendientes;
las correcciones de esta continuación no cambian el ranking ni la taxonomía.

## Validación multinavegador completada

La reanudación en otro entorno completó los 42 casos únicos de Chromium,
Firefox y WebKit, en escritorio y móvil web. El catálogo actualizado contiene
4.330 productos con embeddings. Véase el [informe multinavegador](validacion-multinavegador-2026-10-20.md)
para los resultados agregados, los ajustes de ejecución y las limitaciones.
