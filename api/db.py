"""
Conexiones a Postgres para el API.

Dos modos de conexión, según la RLS:

  * owner  (DATABASE_URL, rol `stalvi`, superusuario): salta la RLS. Se usa SOLO
    en los endpoints de auth (registro/login), que necesitan leer/escribir
    `profiles` sin sesión establecida todavía.
  * app    (APP_DATABASE_URL, rol `app_user`, NO superusuario): la RLS SÍ aplica.
    Se usa en todo endpoint autenticado; fija la identidad con
    `SET app.user_id = <uuid>` para que `current_app_user()` resuelva.

En Supabase esto se sustituye por la conexión con el JWT de `authenticated`
(auth.uid()); el resto del esquema/RLS no cambia (ver supabase/README.md).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()


def _owner_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL no está definida (ver .env).")
    return dsn


def _app_dsn() -> str:
    dsn = os.getenv("APP_DATABASE_URL")
    if not dsn:
        raise RuntimeError("APP_DATABASE_URL no está definida (ver .env).")
    return dsn


@contextmanager
def owner_conn() -> Iterator[psycopg.Connection]:
    """Conexión como owner (salta RLS). Solo para registro/login."""
    with psycopg.connect(_owner_dsn(), row_factory=psycopg.rows.dict_row) as conn:
        register_vector(conn)
        yield conn


@contextmanager
def app_conn(user_id: str) -> Iterator[psycopg.Connection]:
    """
    Conexión como app_user con la identidad de sesión fijada. La RLS aplica:
    el usuario solo ve/gestiona lo suyo. `user_id` viene del JWT verificado.
    """
    with psycopg.connect(_app_dsn(), row_factory=psycopg.rows.dict_row) as conn:
        register_vector(conn)
        # set_config (a diferencia de SET) admite parámetros bind. false =
        # a nivel de sesión, dura lo que la conexión (se cierra al salir del with).
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.user_id', %s, false)", (str(user_id),))
        yield conn
