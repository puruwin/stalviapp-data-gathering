"""Persistencia real en tablas temporales; requiere TEST_DATABASE_URL explícita."""

import copy
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db
from scrapers.consum import ConsumScraper
from scrapers.models import Category, RawProduct

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requiere TEST_DATABASE_URL")


def test_upsert_preserves_ean_context_and_history_snapshot(monkeypatch):
    connect = psycopg.connect
    with connect(os.environ["TEST_DATABASE_URL"]) as connection:
        # Tablas efímeras que ocultan las reales solo en esta conexión.
        for table in ("products", "price_history"):
            connection.execute(f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL)")
            connection.execute(f"ALTER TABLE pg_temp.{table} ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb")

        @contextmanager
        def temporary_connection(*args, **kwargs):
            yield connection

        monkeypatch.setattr(db.psycopg, "connect", temporary_connection)
        monkeypatch.setattr(db, "get_dsn", lambda: "test")
        data = json.loads((Path(__file__).parent / "fixtures/consum/page-0.json").read_text())["products"][0]
        product = ConsumScraper().normalize(RawProduct(str(data["code"]), data), Category("2076", "Entera", "Leche", ""))
        original_price = product.price
        assert db.upsert_products([product, product]) == {"total": 1, "new": 1, "price_changed": 0, "context_changed": 0, "unchanged": 0}
        assert db.upsert_products([product])["unchanged"] == 1
        assert connection.execute("SELECT count(*) FROM pg_temp.price_history").fetchone()[0] == 1
        stored = connection.execute("SELECT source_metadata FROM pg_temp.products WHERE id=%s", (product.id,)).fetchone()[0]
        assert stored["ean"] == data["ean"]
        assert stored["price_context"] == ConsumScraper.PRICE_CONTEXT
        changed = copy.deepcopy(product)
        changed.price += 0.25
        changed.source_metadata["offers"] = []
        assert db.upsert_products([changed])["price_changed"] == 1
        history = connection.execute("SELECT price, source_metadata FROM pg_temp.price_history ORDER BY id").fetchall()
        assert len(history) == 2
        assert float(history[0][0]) == original_price
        assert history[0][1]["offers"] == product.source_metadata["offers"]
        assert history[1][1]["offers"] == []
        assert all(row[1]["price_context"] == ConsumScraper.PRICE_CONTEXT for row in history)
        # Un ámbito nuevo necesita baseline aunque el precio coincida.
        changed.source_metadata['price_context'] = 'consum:online:zone-660:EUR'
        stats = db.upsert_products([changed])
        assert stats['context_changed'] == 1 and stats['price_changed'] == 0
        assert connection.execute('SELECT count(*) FROM pg_temp.price_history').fetchone()[0] == 3
