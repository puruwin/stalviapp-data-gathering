-- 0003 — Usuarios, listas de la compra y RLS (F3). Idempotente.
--
-- Diseño "Supabase-ready": las políticas RLS usan la función current_app_user().
--   * En LOCAL: devuelve el uuid de la variable de sesión app.user_id
--     (SET app.user_id = '<uuid>'), lo que permite probar la RLS sin Supabase.
--   * En SUPABASE: basta redefinir current_app_user() como  SELECT auth.uid()
--     (ver supabase/README.md). Las políticas no cambian.

-- Identidad del usuario en la sesión actual.
CREATE OR REPLACE FUNCTION current_app_user() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

-- Perfil de usuario. En Supabase, id = auth.users.id (poblado por trigger).
CREATE TABLE IF NOT EXISTS profiles (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    display_name  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shopping_lists (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_shopping_lists_user ON shopping_lists (user_id);

CREATE TABLE IF NOT EXISTS shopping_list_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id     UUID NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
    product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity    NUMERIC(10,2) NOT NULL DEFAULT 1,
    checked     BOOLEAN NOT NULL DEFAULT false,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (list_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_list_items_list ON shopping_list_items (list_id);

-- updated_at automático en shopping_lists.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_lists_updated_at ON shopping_lists;
CREATE TRIGGER trg_lists_updated_at
    BEFORE UPDATE ON shopping_lists
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ----------------------------------------------------------------------------
-- RLS: cada usuario solo ve/gestiona lo suyo. FORCE para que aplique también
-- al owner de las tablas (en local nos conectamos como owner).
-- ----------------------------------------------------------------------------
ALTER TABLE profiles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles            FORCE  ROW LEVEL SECURITY;
ALTER TABLE shopping_lists      ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_lists      FORCE  ROW LEVEL SECURITY;
ALTER TABLE shopping_list_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_list_items FORCE  ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_self ON profiles;
CREATE POLICY profiles_self ON profiles
    USING (id = current_app_user())
    WITH CHECK (id = current_app_user());

DROP POLICY IF EXISTS lists_own ON shopping_lists;
CREATE POLICY lists_own ON shopping_lists
    USING (user_id = current_app_user())
    WITH CHECK (user_id = current_app_user());

DROP POLICY IF EXISTS list_items_own ON shopping_list_items;
CREATE POLICY list_items_own ON shopping_list_items
    USING (list_id IN (SELECT id FROM shopping_lists WHERE user_id = current_app_user()))
    WITH CHECK (list_id IN (SELECT id FROM shopping_lists WHERE user_id = current_app_user()));

-- ----------------------------------------------------------------------------
-- Funciones de negocio (RPC). Respetan la RLS del invocante.
-- ----------------------------------------------------------------------------

-- Coste total estimado de una lista (suma de cantidad * precio).
CREATE OR REPLACE FUNCTION list_total(p_list_id uuid)
RETURNS numeric LANGUAGE sql STABLE AS $$
    SELECT COALESCE(SUM(i.quantity * p.price), 0)::numeric(12,2)
    FROM shopping_list_items i
    JOIN products p ON p.id = i.product_id
    WHERE i.list_id = p_list_id;
$$;

-- Serie histórica de precio de un producto (catálogo público).
CREATE OR REPLACE FUNCTION product_price_history(p_product_id text)
RETURNS TABLE(price numeric, price_per_unit numeric, changed_at timestamptz)
LANGUAGE sql STABLE AS $$
    SELECT price, price_per_unit, changed_at
    FROM price_history
    WHERE product_id = p_product_id
    ORDER BY changed_at;
$$;

-- ----------------------------------------------------------------------------
-- Rol de aplicación (NO superusuario) para que la RLS se aplique de verdad.
-- El owner 'stalvi' es superusuario y salta la RLS; la app usa este rol.
-- En Supabase equivale al rol 'authenticated'.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'app_user';
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT ON products, price_history, categories, category_prototypes TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON profiles, shopping_lists, shopping_list_items TO app_user;
GRANT EXECUTE ON FUNCTION current_app_user() TO app_user;
GRANT EXECUTE ON FUNCTION list_total(uuid) TO app_user;
GRANT EXECUTE ON FUNCTION product_price_history(text) TO app_user;
