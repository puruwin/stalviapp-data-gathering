# Validación web multinavegador — 20 de octubre de 2026

Estado: **42 casos únicos validados**. Completa la validación de sesión,
accesibilidad y listas descrita en `validacion-web-2026-10-20.md`.

## Entorno y datos

Esta tarea arrancó desde una copia del repositorio sin los cambios locales de
la conversación anterior y con la base de datos vacía. Se recuperaron los
cambios y las pruebas desde su historial. Se volvió a cargar el catálogo real:
**4.330 productos, 4.330 embeddings y 253 prototipos**.

La app probada es la exportación de producción de Expo SDK 57, servida localmente
con fallback a `index.html`. La API FastAPI y Postgres son reales. Cada caso crea
cuentas efímeras y las elimina junto con sus listas al terminar.

## Resultados agregados de ejecuciones segmentadas

| Motor | Escritorio 1280 × 900 | Web móvil 390 × 844 |
|---|---:|---:|
| Chromium 154.0.8037.57 | 7/7 | 7/7 |
| Firefox 157.0 | 7/7 | 7/7 |
| WebKit 27.2 | 7/7 | 7/7 |

Los resultados se agregan de tres series: 18 casos aprobados en la serie inicial
(14 de Chromium y cuatro de Firefox de escritorio), tres casos de Firefox de
escritorio aprobados en la repetición y los 21 casos restantes aprobados en la
última serie, que terminó con `21 passed (7.8m)`. Los intentos interrumpidos y
los fallos por tiempo anteriores se describen en los ajustes de herramientas.

Son siete casos por combinación de motor y tamaño:

1. Token guardado inválido, limpieza de sesión y navegación atrás protegida.
2. HTTP 401 durante la sesión, vuelta al login y ausencia de reintentos del token.
3. Credenciales incorrectas, caída del login y recuperación.
4. Caída de listas, creación y búsqueda; conservación de sesión y reintentos.
5. Recarga, navegación atrás y cambio de cuenta sin mostrar listas ajenas.
6. HTTP 401 tardío de la cuenta anterior sin cerrar la nueva sesión.
7. Login, crear lista, buscar, añadir, aumentar/reducir cantidad, total, marcar
   comprado, quitar, renombrar, volver a añadir, vaciar y borrar.

Las caídas y los 401 controlados se simulan interceptando tráfico. El recorrido
de compra usa productos, embeddings, persistencia y cálculos del backend real.
Los controles se seleccionan por sus nombres accesibles, sin clicks forzados;
también se comprueba el estado de las casillas y el desbordamiento horizontal.

## Ajustes de las herramientas de validación

- `cdn.playwright.dev` ya permite descargar Firefox y WebKit mediante la
  alternativa oficial del instalador. Chromium usa el binario del sistema.
- Las bibliotecas que faltaban en WebKit se extrajeron de paquetes oficiales de
  Debian en el espacio de trabajo. Se comprobó su arranque y renderización.
  El comprobador de `ldconfig` no reconoce esta instalación local; los detalles
  y la configuración están en `app/e2e/README.md`. TLS permanece verificado.
- El tiempo total de cada caso pasó de 60 a 120 segundos para incluir la
  preparación y la carga de Firefox. Las comprobaciones de estados conservan
  su espera máxima de 10 segundos. Los primeros intentos agotaron el tiempo;
  la repetición de los tres casos pendientes de Firefox de escritorio pasó.
- Se mantiene un proceso y se usan temporales en `/tmp`, que reside en memoria.
  Dos procesos simultáneos empeoraron el arranque en este entorno.
- Metro se limita a dos procesos para compilar la web.

## Otras comprobaciones y límites

TypeScript de la app y de las pruebas y la exportación web pasan. Al terminar,
la base de datos contiene cero perfiles, listas e items de prueba; el catálogo
conserva los 4.330 productos con embeddings. Las pruebas
se conservan en `app/e2e/` y se ejecutan con `npm run test:web`; las instrucciones
de preparación y las variables admitidas están en `app/e2e/README.md`.

La cobertura móvil es emulación web. Firefox usa viewport estrecho y eventos
táctiles; WebKit aproxima el motor de Safari. No se ha probado un iPhone físico
ni los builds nativos. Estos resultados funcionales no son una medición de
rendimiento ni una auditoría completa de accesibilidad.

La relevancia de búsquedas como «leche», «agua» y «plátano» y el mapeo de Turrones
siguen pendientes; esta continuación no modifica el ranking ni la taxonomía.
