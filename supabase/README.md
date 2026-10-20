# supabase/

Plan de portabilidad a Supabase. Hoy desarrollamos sobre Postgres local
(docker-compose) con un esquema **Supabase-ready**; aquí se documenta qué cambia
al mover la BD a Supabase (previsto para el despliegue, junto con F4).

## Qué se reutiliza tal cual
- Todas las migraciones de `db/migrations/` (mismo SQL plano).
- Las tablas de usuario (`profiles`, `shopping_lists`, `shopping_list_items`).
- Las políticas **RLS** y las funciones RPC (`list_total`, `product_price_history`).

## Qué cambia al pasar a Supabase
1. **Identidad.** Redefinir la función de identidad para usar el JWT de Supabase:
   ```sql
   CREATE OR REPLACE FUNCTION current_app_user() RETURNS uuid
   LANGUAGE sql STABLE AS $$ SELECT auth.uid() $$;
   ```
   Las políticas RLS no cambian (siguen usando `current_app_user()`).

2. **profiles ↔ auth.users.** En Supabase el usuario vive en `auth.users`. Se
   sincroniza `profiles` con un trigger:
   ```sql
   -- profiles.id = auth.users.id ; crear perfil al registrarse
   CREATE OR REPLACE FUNCTION handle_new_user() RETURNS trigger
   LANGUAGE plpgsql SECURITY DEFINER AS $$
   BEGIN
       INSERT INTO public.profiles (id, email) VALUES (NEW.id, NEW.email);
       RETURN NEW;
   END; $$;
   CREATE TRIGGER on_auth_user_created
       AFTER INSERT ON auth.users
       FOR EACH ROW EXECUTE FUNCTION handle_new_user();
   ```

3. **Rol de aplicación.** En local usamos el rol `app_user` (no superusuario) para
   que la RLS se aplique. En Supabase ese papel lo cumple el rol `authenticated`;
   ajustar los `GRANT` a `authenticated` en lugar de `app_user`.

4. **Datos de catálogo.** El scraper seguiría escribiendo `products`/`price_history`
   (con la `service_role` key o una conexión directa a la BD de Supabase).

## Nota
El scraper se conecta como owner (`stalvi`, `DATABASE_URL`). La app usará el rol
`app_user` (`APP_DATABASE_URL`) para que la RLS proteja los datos de usuario.
