# Scraping de Supermercado Dia - Base de Datos PostgreSQL

Este proyecto realiza scraping de productos del supermercado Dia y los almacena en una base de datos PostgreSQL.

## Requisitos Previos

1. **PostgreSQL instalado y ejecutándose**
   - Descarga desde: https://www.postgresql.org/download/
   - Asegúrate de que el servicio esté corriendo

2. **Python 3.7 o superior**

## Configuración

### 1. Crear la Base de Datos

Conecta a PostgreSQL y crea la base de datos:

```sql
CREATE DATABASE stalviapp;
```

### 2. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=stalviapp
DB_USER=postgres
DB_PASSWORD=tu_password
```

**Nota:** Reemplaza `tu_password` con tu contraseña de PostgreSQL.

### 3. Instalar Dependencias

Instala las dependencias de Python:

```bash
pip install -r requirements.txt
```

## Uso

### Ejecutar el Scraper

Desde el directorio `scripts`, ejecuta:

```bash
python dia_scrap.py
```

O desde la raíz del proyecto:

```bash
python scripts/dia_scrap.py
```

El script:
1. Inicializará la base de datos (creará las tablas si no existen)
2. Obtendrá todas las categorías y subcategorías de Dia
3. Procesará cada subcategoría y guardará los productos en la base de datos
4. Actualizará precios si los productos ya existen
5. Mantendrá un historial de cambios de precio

## Estructura de la Base de Datos

### Tabla `categories`
Almacena las categorías y subcategorías:
- `id`: ID único (auto-incremental)
- `external_id`: ID de la API de Dia (único)
- `name`: Nombre de la categoría
- `link`: URL de la categoría
- `parent_category`: Nombre de la categoría padre
- `created_at`: Fecha de creación

### Tabla `products`
Almacena los productos con su información actual:
- `id`: ID único (auto-incremental)
- `display_name`: Nombre del producto
- `brand`: Marca (opcional)
- `category_id`: Referencia a la categoría
- `current_price`: Precio actual
- `current_price_per_unit`: Precio por unidad
- `measure_unit`: Unidad de medida
- `first_seen`: Fecha de primera detección
- `last_updated`: Fecha de última actualización

### Tabla `price_history`
Mantiene el historial de cambios de precio:
- `id`: ID único (auto-incremental)
- `product_id`: Referencia al producto
- `price`: Precio registrado
- `price_per_unit`: Precio por unidad registrado
- `recorded_at`: Fecha y hora del registro

## Características

- **Inserción de productos nuevos**: Los productos nuevos se insertan automáticamente
- **Actualización de precios**: Si un producto ya existe, se actualiza su precio
- **Historial de precios**: Cada cambio de precio se registra en `price_history`
- **Manejo de transacciones**: Los errores se manejan con rollback automático
- **Detección de duplicados**: Evita duplicados usando `display_name`, `brand` y `category_id`

## Notas

- El script respeta los límites de la API y usa headers apropiados
- Los errores se registran en la consola con mensajes descriptivos
- La conexión a la base de datos se cierra automáticamente al finalizar

## Próximos Pasos

Este proyecto está preparado para ser usado con una API REST en Node.js. La estructura de la base de datos permite consultas eficientes para:
- Obtener productos por categoría
- Consultar historial de precios
- Buscar productos por nombre o marca
- Analizar tendencias de precios

