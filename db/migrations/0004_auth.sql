-- 0004 — Password para el login propio del MVP (F4). Idempotente.
--
-- El MVP usa un API FastAPI con JWT propio (ver api/). El login valida
-- credenciales contra profiles, así que aquí se añade el hash de contraseña.
--
-- Nota Supabase: al desplegar, las contraseñas las gestiona auth.users y esta
-- columna deja de usarse (profiles se sincroniza por trigger, sin password_hash).
-- Se mantiene NULLABLE precisamente para ser compatible con perfiles creados
-- por Supabase Auth.

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- El rol de aplicación necesita leer/escribir el hash durante login/registro.
-- (Los endpoints de auth se conectan como owner, pero dejamos el grant coherente
--  por si en el futuro se gestionan desde el rol de app.)
GRANT SELECT, INSERT, UPDATE ON profiles TO app_user;
