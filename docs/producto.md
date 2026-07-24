# Prototipo de producto — Stalvi

Qué información y funcionalidades ofrecemos al usuario. El MVP se centra en **hacer
la lista de la compra y ver cuánto vas a gastar**.

## Datos disponibles por producto
Ya en la BD (Mercadona): `name`, `price`, `price_per_unit`, `unit`, `brand`,
`master_category_id` (taxonomía transversal), `image_url`, `url`, histórico de
precios (`price_history`) y `embedding` (búsqueda semántica).

## MVP (ahora)
1. **Registro / login** — Supabase Auth (se integra en F4).
2. **Buscar productos** — búsqueda semántica por embeddings (F2): el usuario escribe
   "leche sin lactosa" y obtiene resultados relevantes.
3. **Listas de la compra** — crear listas, añadir productos con cantidad, marcar como
   comprado. Cada usuario solo ve las suyas (RLS).
4. **Gasto total estimado** — `list_total(list_id)` suma cantidad × precio en vivo.
5. **Histórico de precio** — `product_price_history(product_id)` para mostrar la
   evolución del precio de un producto.

## Modelo de datos (F3)
| Tabla | Para qué |
|-------|----------|
| `profiles` | Perfil del usuario (id = auth.users.id en Supabase) |
| `shopping_lists` | Listas del usuario |
| `shopping_list_items` | Ítems (producto + cantidad + comprado) |
| RPC `list_total` | Coste total estimado de una lista |
| RPC `product_price_history` | Serie de precios de un producto |

Seguridad: **RLS** activa; cada usuario solo accede a sus filas
(`current_app_user()`, portable a `auth.uid()` en Supabase).

## Roadmap funcional (después del MVP)
- **Favoritos** — acceso rápido a productos habituales.
- **Alertas de precio** — avisar cuando un producto baja de un precio objetivo
  (se apoya en `price_history`).
- **Comparativa entre súpers** — cuando haya más de un supermercado, comparar la
  misma lista en varias cadenas (la taxonomía maestra ya lo permite).
- **Recomendaciones / lista inteligente** — sugerir productos por similitud
  (embeddings) o por hábitos de compra.
