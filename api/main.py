"""
API FastAPI del MVP de Stalvi (F4).

Fino sobre el backend F0–F3: reutiliza el modelo de embeddings (búsqueda
semántica) y el esquema Postgres con RLS. Auth con JWT propio (ver auth.py).

Endpoints:
  POST /auth/register            registro (email + password)
  POST /auth/login               login → JWT
  GET  /auth/me                  perfil del token
  GET  /search?q=&k=             búsqueda semántica de productos
  GET  /lists                    listas del usuario (con nº items y total)
  POST /lists                    crear lista
  GET  /lists/{id}               lista + items (con datos de producto)
  PATCH /lists/{id}              renombrar lista
  DELETE /lists/{id}             borrar lista
  DELETE /lists/{id}/items       vaciar lista (borra todos los items)
  POST /lists/{id}/items         añadir/actualizar item (upsert por producto)
  PATCH /lists/{id}/items/{iid}  cambiar cantidad / marcar comprado
  DELETE /lists/{id}/items/{iid} quitar item
  GET  /lists/{id}/total         gasto total estimado (RPC list_total)

Arranque:  uvicorn api.main:app --reload  (desde la raíz del repo)
"""

from __future__ import annotations

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import auth as auth_mod
from .db import app_conn, owner_conn
from .schemas import (
    ItemAddIn,
    ItemUpdateIn,
    ListCreateIn,
    ListUpdateIn,
    LoginIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from .search import search_products

app = FastAPI(title="Stalvi API", version="0.1.0")

# CORS abierto para el dev de Expo (web en localhost:8081, móvil por LAN).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_bearer = HTTPBearer(auto_error=True)


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Valida el JWT del header Authorization y devuelve {id, email}."""
    try:
        payload = auth_mod.decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")
    return {"id": payload["sub"], "email": payload.get("email")}


def _owns_list(user_id: str, list_id: str) -> None:
    """Lanza 404 si la lista no existe o no es del usuario (RLS ya la filtra)."""
    with app_conn(user_id) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM shopping_lists WHERE id = %s", (list_id,))
        if cur.fetchone() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lista no encontrada")


# --- Salud ---
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Auth ------------------------------------------------------------------
@app.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn) -> TokenOut:
    email = body.email.lower()
    # owner_conn: en registro no hay sesión aún y la RLS de profiles bloquearía.
    with owner_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM profiles WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(status.HTTP_409_CONFLICT, "El email ya está registrado")
        cur.execute(
            "INSERT INTO profiles (email, display_name, password_hash) "
            "VALUES (%s, %s, %s) RETURNING id",
            (email, body.display_name, auth_mod.hash_password(body.password)),
        )
        user_id = str(cur.fetchone()["id"])
        conn.commit()
    token = auth_mod.issue_token(user_id, email)
    return TokenOut(
        token=token,
        user=UserOut(id=user_id, email=email, display_name=body.display_name),
    )


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn) -> TokenOut:
    email = body.email.lower()
    with owner_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, display_name, password_hash FROM profiles WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
    if not row or not auth_mod.verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    user_id = str(row["id"])
    token = auth_mod.issue_token(user_id, row["email"])
    return TokenOut(
        token=token,
        user=UserOut(id=user_id, email=row["email"], display_name=row["display_name"]),
    )


@app.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> UserOut:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, email, display_name FROM profiles WHERE id = %s", (user["id"],)
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil no encontrado")
    return UserOut(id=str(row["id"]), email=row["email"], display_name=row["display_name"])


# --- Búsqueda --------------------------------------------------------------
@app.get("/search")
def search(
    q: str = Query(min_length=1),
    k: int = Query(default=20, ge=1, le=50),
    user: dict = Depends(current_user),
) -> list[dict]:
    return search_products(user["id"], q, k)


# --- Listas ----------------------------------------------------------------
@app.get("/lists")
def get_lists(user: dict = Depends(current_user)) -> list[dict]:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT sl.id, sl.name,
                   COUNT(i.id)       AS item_count,
                   list_total(sl.id) AS total
            FROM shopping_lists sl
            LEFT JOIN shopping_list_items i ON i.list_id = sl.id
            GROUP BY sl.id, sl.name, sl.created_at
            ORDER BY sl.created_at DESC
            """
        )
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "item_count": int(r["item_count"]),
                "total": float(r["total"]) if r["total"] is not None else 0.0,
            }
            for r in cur.fetchall()
        ]


@app.post("/lists", status_code=201)
def create_list(body: ListCreateIn, user: dict = Depends(current_user)) -> dict:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO shopping_lists (user_id, name) VALUES (%s, %s) RETURNING id, name",
            (user["id"], body.name),
        )
        row = cur.fetchone()
        conn.commit()
    return {"id": str(row["id"]), "name": row["name"]}


@app.get("/lists/{list_id}")
def get_list(list_id: str, user: dict = Depends(current_user)) -> dict:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name FROM shopping_lists WHERE id = %s", (list_id,))
        lst = cur.fetchone()
        if lst is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lista no encontrada")
        cur.execute(
            """
            SELECT i.id, i.product_id, i.quantity, i.checked,
                   p.name, p.price, p.price_per_unit, p.unit, p.brand, p.image_url
            FROM shopping_list_items i
            JOIN products p ON p.id = i.product_id
            WHERE i.list_id = %s
            ORDER BY i.added_at
            """,
            (list_id,),
        )
        items = []
        for r in cur.fetchall():
            items.append(
                {
                    "id": str(r["id"]),
                    "product_id": r["product_id"],
                    "quantity": float(r["quantity"]),
                    "checked": r["checked"],
                    "name": r["name"],
                    "price": float(r["price"]) if r["price"] is not None else None,
                    "price_per_unit": float(r["price_per_unit"])
                    if r["price_per_unit"] is not None
                    else None,
                    "unit": r["unit"],
                    "brand": r["brand"],
                    "image_url": r["image_url"],
                }
            )
    return {"id": str(lst["id"]), "name": lst["name"], "items": items}


@app.patch("/lists/{list_id}")
def rename_list(
    list_id: str, body: ListUpdateIn, user: dict = Depends(current_user)
) -> dict:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE shopping_lists SET name = %s WHERE id = %s RETURNING id, name",
            (body.name, list_id),
        )
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lista no encontrada")
    return {"id": str(row["id"]), "name": row["name"]}


@app.delete("/lists/{list_id}", status_code=204)
def delete_list(list_id: str, user: dict = Depends(current_user)) -> None:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM shopping_lists WHERE id = %s", (list_id,))
        conn.commit()


@app.delete("/lists/{list_id}/items", status_code=204)
def empty_list(list_id: str, user: dict = Depends(current_user)) -> None:
    """Vacía la lista: borra todos sus items (la lista se mantiene)."""
    _owns_list(user["id"], list_id)
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM shopping_list_items WHERE list_id = %s", (list_id,))
        conn.commit()


@app.post("/lists/{list_id}/items", status_code=201)
def add_item(
    list_id: str, body: ItemAddIn, user: dict = Depends(current_user)
) -> dict:
    _owns_list(user["id"], list_id)
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        # Upsert por (lista, producto): si ya está, suma la cantidad.
        cur.execute(
            """
            INSERT INTO shopping_list_items (list_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON CONFLICT (list_id, product_id)
            DO UPDATE SET quantity = shopping_list_items.quantity + EXCLUDED.quantity
            RETURNING id, product_id, quantity, checked
            """,
            (list_id, body.product_id, body.quantity),
        )
        row = cur.fetchone()
        conn.commit()
    return {
        "id": str(row["id"]),
        "product_id": row["product_id"],
        "quantity": float(row["quantity"]),
        "checked": row["checked"],
    }


@app.patch("/lists/{list_id}/items/{item_id}")
def update_item(
    list_id: str,
    item_id: str,
    body: ItemUpdateIn,
    user: dict = Depends(current_user),
) -> dict:
    if body.quantity is None and body.checked is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nada que actualizar")
    sets, params = [], []
    if body.quantity is not None:
        sets.append("quantity = %s")
        params.append(body.quantity)
    if body.checked is not None:
        sets.append("checked = %s")
        params.append(body.checked)
    params.extend([item_id, list_id])
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE shopping_list_items SET {', '.join(sets)} "
            "WHERE id = %s AND list_id = %s "
            "RETURNING id, product_id, quantity, checked",
            params,
        )
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item no encontrado")
    return {
        "id": str(row["id"]),
        "product_id": row["product_id"],
        "quantity": float(row["quantity"]),
        "checked": row["checked"],
    }


@app.delete("/lists/{list_id}/items/{item_id}", status_code=204)
def delete_item(
    list_id: str, item_id: str, user: dict = Depends(current_user)
) -> None:
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM shopping_list_items WHERE id = %s AND list_id = %s",
            (item_id, list_id),
        )
        conn.commit()


@app.get("/lists/{list_id}/total")
def list_total(list_id: str, user: dict = Depends(current_user)) -> dict:
    _owns_list(user["id"], list_id)
    with app_conn(user["id"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT list_total(%s) AS total", (list_id,))
        total = cur.fetchone()["total"]
    return {"total": float(total) if total is not None else 0.0}
