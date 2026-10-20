"""Esquemas Pydantic de entrada/salida del API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    display_name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None


class TokenOut(BaseModel):
    token: str
    user: UserOut


# --- Listas ---
class ListCreateIn(BaseModel):
    name: str = Field(min_length=1)


class ListUpdateIn(BaseModel):
    name: str = Field(min_length=1)


class ListOut(BaseModel):
    id: str
    name: str


class ItemAddIn(BaseModel):
    product_id: str
    quantity: float = Field(default=1, gt=0)


class ItemUpdateIn(BaseModel):
    quantity: Optional[float] = Field(default=None, gt=0)
    checked: Optional[bool] = None
