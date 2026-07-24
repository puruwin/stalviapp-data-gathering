"""Tests de utilidades de embeddings que no requieren modelo ni BD."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from embeddings.store import product_text, to_numpy


def test_product_text_with_brand():
    assert product_text("Leche entera", "Hacendado") == "Leche entera Hacendado"


def test_product_text_without_brand():
    assert product_text("Leche entera", None) == "Leche entera"


def test_to_numpy_from_list():
    v = to_numpy([1, 2, 3])
    assert isinstance(v, np.ndarray)
    assert v.dtype == np.float32
    assert v.tolist() == [1.0, 2.0, 3.0]


def test_to_numpy_from_ndarray():
    v = to_numpy(np.array([1.0, 2.0], dtype=np.float64))
    assert v.dtype == np.float32
