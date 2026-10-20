-- Verificación de F3: RLS de usuarios + list_total.
-- Ejecuta:  docker compose exec -T db psql -U stalvi -d stalvi < db/verify_f3.sql
-- Crea dos usuarios de prueba, comprueba el coste total de una lista y que un
-- usuario no ve las listas de otro (RLS).

DO $$
DECLARE
    a uuid := '11111111-1111-1111-1111-111111111111';
    b uuid := '22222222-2222-2222-2222-222222222222';
    l uuid;
    p1 text; pr1 numeric; p2 text; pr2 numeric;
    total numeric; expected numeric; visible_b int;
BEGIN
    -- Limpieza idempotente (cada usuario borra lo suyo).
    PERFORM set_config('app.user_id', a::text, true);
    DELETE FROM shopping_lists WHERE user_id = a;
    PERFORM set_config('app.user_id', b::text, true);
    DELETE FROM shopping_lists WHERE user_id = b;

    -- Dos productos reales con precio.
    SELECT id, price INTO p1, pr1 FROM products WHERE price IS NOT NULL ORDER BY id LIMIT 1;
    SELECT id, price INTO p2, pr2 FROM products WHERE price IS NOT NULL ORDER BY id OFFSET 1 LIMIT 1;

    -- Usuario A: crea perfil, lista e ítems.
    PERFORM set_config('app.user_id', a::text, true);
    INSERT INTO profiles(id, email) VALUES (a, 'a@test.com') ON CONFLICT (id) DO NOTHING;
    INSERT INTO shopping_lists(user_id, name) VALUES (a, 'Compra semanal') RETURNING id INTO l;
    INSERT INTO shopping_list_items(list_id, product_id, quantity) VALUES (l, p1, 2), (l, p2, 3);

    total := list_total(l);
    expected := round(2 * pr1 + 3 * pr2, 2);

    -- Usuario B: no debe ver las listas de A.
    PERFORM set_config('app.user_id', b::text, true);
    INSERT INTO profiles(id, email) VALUES (b, 'b@test.com') ON CONFLICT (id) DO NOTHING;
    SELECT count(*) INTO visible_b FROM shopping_lists;

    RAISE NOTICE 'list_total = % (esperado %) -> match=%', total, expected, (total = expected);
    RAISE NOTICE 'listas de A visibles por B = % (esperado 0) -> ok=%', visible_b, (visible_b = 0);
END $$;
