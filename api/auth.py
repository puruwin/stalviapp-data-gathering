"""
Autenticación del MVP: hash de contraseña (stdlib) + JWT propio (PyJWT).

Decisión F4: login simple contra `profiles`. Al desplegar se sustituye por
Supabase Auth (el front pasaría el JWT de Supabase y la BD usaría auth.uid()).
Aquí el JWT lo emite y verifica este API.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

# --- Configuración ---------------------------------------------------------
JWT_SECRET = os.getenv("API_JWT_SECRET", "dev-insecure-secret-cambiar-en-prod")
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = int(os.getenv("API_JWT_TTL_HOURS", "168"))  # 7 días

_PBKDF2_ROUNDS = 240_000


# --- Hash de contraseña (PBKDF2-HMAC-SHA256, sin dependencias externas) -----
def hash_password(password: str) -> str:
    """Devuelve 'pbkdf2_sha256$rounds$salt_hex$hash_hex'."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Verifica una contraseña contra el hash almacenado (comparación constante)."""
    if not stored:
        return False
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds_s)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# --- JWT -------------------------------------------------------------------
def issue_token(user_id: str, email: str) -> str:
    """Emite un JWT con el id de usuario (sub) y su email."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica y valida un JWT. Lanza jwt.PyJWTError si no es válido."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
