# Pruebas web de Stalvi

Las pruebas usan la interfaz, la API local y productos reales con embeddings.
Se crean cuentas efímeras y se eliminan al terminar, con sus listas, incluso si
un test falla. Ejecutar contra una base de desarrollo con las migraciones
aplicadas; la limpieza usa el entorno Python y `DATABASE_URL` del backend.

## Preparación

1. Arrancar Postgres y la API según el README de la raíz. El catálogo debe tener
   embeddings (`python scraper/embed.py all`). Usar la misma caché de fastembed
   al arrancar la API para evitar otra descarga del modelo.
2. Desde `app/`, instalar dependencias y navegadores:

   ```sh
   npm ci
   npx playwright install chromium firefox webkit
   # Si faltan bibliotecas del sistema: npx playwright install-deps
   ```

3. Ejecutar:

   ```sh
   npm run test:web
   ```

Playwright levanta Expo en `http://localhost:8082` y lo cierra al terminar.
La API debe estar disponible en `http://127.0.0.1:8000`.

La matriz incluye Chromium, Firefox y WebKit a 1280 × 900 y 390 × 844. Los
proyectos estrechos usan eventos táctiles; Firefox usa viewport móvil, sin la
opción `isMobile` que su motor no admite. WebKit aproxima el motor de Safari;
estas pruebas no sustituyen una comprobación en Safari de un iPhone real.

Cada caso dispone de 120 segundos en total, incluida la preparación de cuentas
y la carga del navegador; las comprobaciones de cada estado esperan hasta 10
segundos. Se ejecuta un proceso; en el entorno cloud conviene mantener ese límite
y usar los temporales de `/tmp`, que reside en memoria. La ejecución en paralelo
resultó más lenta y agotó el tiempo de casos que pasan con un solo proceso.

## Entorno cloud actual

Chromium ya está instalado. Para usarlo sin descargar otro binario:

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
E2E_PROXY_SERVER=http://proxy:8080 \
npm run test:web -- --project=desktop-chromium --project=mobile-chromium
```

El navegador necesita acceso a su almacén NSS con la CA del proxy importada. Se
mantiene la verificación TLS. `cdn.playwright.dev` ya está permitido y Firefox y
WebKit se han descargado. Las primeras URLs redirigen a otro dominio bloqueado;
el instalador utiliza después su alternativa oficial en el mismo CDN permitido.
La descarga de Chrome for Testing redirige a `storage.googleapis.com`; en este
entorno se usa el Chromium del sistema.

El entorno no permite instalar paquetes del sistema con `install-deps`. Las
bibliotecas de WebKit se han extraído de paquetes oficiales de Debian en
`/workspace/.cache/webkit-libs/extracted/`. Su lanzador reemplaza
`LD_LIBRARY_PATH`, por lo que las bibliotecas se enlazan también en `sys/lib`
de cada MiniBrowser. Playwright consulta `ldconfig` para validar `libGLESv2`,
que no registra estas bibliotecas locales: tras verificar el arranque y la
renderización se usa `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1` para las
pruebas de este entorno. Esta opción no desactiva TLS.

La configuración limita Metro a dos procesos. Para probar una exportación ya
compilada se puede usar `E2E_WEB_URL` con un servidor local que sirva los archivos
de la exportación y devuelva `index.html` para las rutas de la app.

## Cobertura

- Login → crear lista → buscar «leche» → añadir → subir/bajar cantidad →
  comprobar el total → marcar comprado → quitar → renombrar → volver a añadir
  → vaciar → borrar. La búsqueda y los cálculos usan el backend real.
- Token guardado inválido, recarga y navegación atrás a una ruta protegida.
- HTTP 401 durante la sesión y respuesta 401 tardía de la cuenta anterior.
- Credenciales incorrectas; caída de servidor al recargar, login, búsqueda y
  creación de lista; recuperación mediante reintento. Las caídas y el 401
  controlado se simulan interceptando tráfico; no se detiene la API compartida.
- Sesión persistida, navegación atrás y cambio de cuenta sin recargar el
  documento, para comprobar que se limpia la caché de listas.
- Campos y controles seleccionados por sus nombres accesibles, estado marcado
  de las casillas y ausencia de desbordamiento horizontal en el recorrido.

No se simulan los productos ni los embeddings para el recorrido principal. El
test comprueba el flujo funcional, no la calidad del ranking semántico.

## Configuración y evidencias

- `E2E_API_URL`: URL alternativa de la API; también se pasa a Expo.
- `E2E_WEB_URL`: app ya arrancada; en ese caso Playwright no levanta otro servidor.
- `E2E_PYTHON`: ejecutable Python para limpiar las cuentas; por defecto
  `../.venv/bin/python`.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`: Chromium instalado en el sistema.
- `E2E_PROXY_SERVER`: proxy del navegador, con bypass para localhost.
- `PLAYWRIGHT_BROWSERS_PATH`: caché de binarios si se quiere usar otra ubicación.

Se guarda informe HTML en `playwright-report/` y captura/traza de cada fallo en
`test-results/`. Esas carpetas están excluidas de Git porque pueden contener
sesiones de prueba. Para abrir una traza: `npx playwright show-trace <ruta.zip>`.

TypeScript de app y pruebas:

```sh
npx tsc --noEmit
npx tsc --noEmit -p e2e/tsconfig.json
```
