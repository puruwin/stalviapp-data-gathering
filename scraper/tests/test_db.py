"""Tests de la lógica pura de persistencia (sin BD)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import _price_eq


def test_price_eq_both_none():
    assert _price_eq(None, None) is True


def test_price_eq_one_none():
    assert _price_eq(None, 1.0) is False
    assert _price_eq(1.0, None) is False


def test_price_eq_equal_within_cents():
    assert _price_eq(1.20, 1.201) is True
    assert _price_eq(1.999, 2.0) is True


def test_price_eq_different():
    assert _price_eq(1.20, 1.25) is False
