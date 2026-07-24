# F3 — Modelo de datos de usuarios + funcionalidades

> Depende de F1 (productos/precios). Modela usuarios, listas de la compra y define qué se ofrece al usuario.

## Objetivo
Diseñar el modelo relacional de usuarios y listas de la compra con seguridad por fila (RLS), y las funciones que dan valor: coste total de una lista, precios, histórico. Prototipar el alcance funcional del producto.

## Contexto / estado actual
- **No existe nada de usuarios** hoy (ni tabla, ni auth, ni listas).
- Con Supabase, la identidad vive en `auth.users`; nuestras tablas la referencian por `user_id UUID`.
- Productos y `price_history` ya existen (F1).

## Tareas
1. **Schema en `db/`:**
   - `profiles(user_id UUID PK REFERENCES auth.users, display_name, created_at)`.
   - `shopping_lists(id, user_id, name, created_at, updated_at)`.
   - `shopping_list_items(id, list_id FK, product_id FK, quantity, checked, added_at)`.
   - `favorites(user_id, product_id, added_at)` (PK compuesta).
   - `price_alerts(id, user_id, product_id, target_price, is_active, triggered_at)`.
2. **RLS:** activar en todas las tablas de usuario; políticas `user_id = auth.uid()` para select/insert/update/delete. Los productos/precios son de solo lectura pública.
3. **Funciones RPC / vistas:**
   - `list_total(list_id)`: suma `quantity * price` de los ítems (gasto estimado).
   - `product_price_history(product_id)`: serie temporal desde `price_history`.
   - `cheapest_in_category(master_category_id)`: producto más barato por categoría/unidad.
4. **Documento de producto** (`docs/producto.md`): qué información y funcionalidades ofrecer en el MVP y después:
   - MVP: registrarse, buscar productos, crear lista, ver **gasto total** estimado.
   - Siguiente: favoritos, alertas de precio, histórico de precio por producto, (a futuro) comparativa entre súpers.

## Decisiones abiertas
- Auth: ¿Supabase Auth (email/OAuth) — recomendado — o propia?
- ¿`profiles` separada de `auth.users` (recomendado) o metadatos en el propio auth?
- Alcance exacto del MVP funcional a confirmar con el documento de producto.

## Criterios de aceptación
- Un usuario de prueba crea lista + ítems vía API; otro usuario **no** puede verlos (RLS).
- `list_total(list_id)` devuelve el gasto correcto.
- `docs/producto.md` define el alcance MVP + roadmap funcional.

## Verificación
```sql
-- como usuario A: crear lista e ítems, luego:
SELECT list_total('<list_id>');            -- gasto esperado
-- como usuario B: SELECT * FROM shopping_lists;  -> no ve las de A (RLS)
```
