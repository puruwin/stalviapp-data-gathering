"""Integración contra Postgres local: datos de prueba dentro de una transacción.

Ejecutar con la BD de desarrollo levantada:
  .venv/bin/python -m pytest api/tests/test_catalogue.py
No se modifican productos del scraper ni se confirma ninguna escritura.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api import catalogue
from api.db import owner_conn
from api.main import app, current_user


@pytest.fixture
def dataset(monkeypatch):
    prefix = f'backoffice-test-{uuid4().hex}'
    now = datetime.now(timezone.utc)
    with owner_conn() as conn:
        try:
            for suffix, name, price in [('down', 'Leche de prueba', 2), ('up', 'Avena de prueba', 4), ('single', 'Registro único', 3), ('null', 'Sin precio', None)]:
                pid = f'{prefix}-{suffix}'
                conn.execute("""INSERT INTO products (id,name,supermarket,category,brand,price,last_seen)
                    VALUES (%s,%s,'mercadona',%s,'Marca prueba',%s,%s)""",
                    (pid, name, f'{prefix} > Subcategoría', price, now-timedelta(hours=1)))
                conn.execute('INSERT INTO price_history (product_id,price,changed_at) VALUES (%s,%s,%s)',
                             (pid, 3 if suffix in ('down','up') else price, now-timedelta(days=60)))
                if suffix in ('down','up'):
                    conn.execute('INSERT INTO price_history (product_id,price,changed_at) VALUES (%s,%s,%s)',
                                 (pid, price, now-timedelta(days=2)))
            # Las consultas se verifican con los permisos del mismo rol que el API.
            conn.execute('SET LOCAL ROLE app_user')
            @contextmanager
            def connection(_user_id):
                yield conn
            monkeypatch.setattr(catalogue, 'app_conn', connection)
            yield prefix
        finally:
            conn.rollback()


@pytest.fixture
def client(dataset):
    app.dependency_overrides[current_user] = lambda: {'id':'00000000-0000-0000-0000-000000000000'}
    try:
        with TestClient(app) as client:
            yield client, dataset
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_pagination_filters_and_nulls(client):
    http, prefix = client
    response = http.get('/catalogue/products', params={'category':prefix,'page_size':2})
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 4 and len(data['items']) == 2
    second = http.get('/catalogue/products', params={'category':prefix,'page_size':2,'page':2}).json()
    assert {p['id'] for p in data['items']}.isdisjoint(p['id'] for p in second['items'])
    down = http.get('/catalogue/products', params={'category':prefix,'change':'down'}).json()
    assert down['total'] == 1 and down['items'][0]['id'] == f'{prefix}-down'
    assert down['items'][0]['previous_price'] == 3 and down['items'][0]['change_percent'] == -33.33
    up = http.get('/catalogue/products', params={'category':prefix,'change':'up'}).json()
    assert up['total'] == 1 and up['items'][0]['id'] == f'{prefix}-up'
    unknown = http.get('/catalogue/products', params={'category':prefix,'change':'unknown'}).json()
    assert unknown['total'] == 2
    literal = http.get('/catalogue/products', params={'category':prefix,'q':'%'}).json()
    assert literal['total'] == 0
    missing_price = http.get(f'/catalogue/products/{prefix}-null').json()
    assert missing_price['price'] is None and missing_price['change_percent'] is None
    subset = http.get('/catalogue/products', params={'ids':f'{prefix}-single'}).json()
    assert subset['total'] == 1


def test_history_preserves_baseline_and_single_observation(client):
    http, prefix = client
    data = http.get(f'/catalogue/products/{prefix}-down/history?days=30').json()
    assert data['observation_count'] == 2
    assert [p['price'] for p in data['points']] == [3, 2]
    assert data['points'][0]['changed_at'] < data['start']
    single = http.get(f'/catalogue/products/{prefix}-single/history?days=30').json()
    assert single['observation_count'] == 1 and len(single['points']) == 1
    assert single['points'][0]['price'] == 3
    assert http.get(f'/catalogue/products/{prefix}-missing/history').status_code == 404


def test_history_and_variation_only_compare_same_price_context(client):
    from psycopg.types.json import Jsonb
    http, prefix = client
    identity = f'{prefix}-down'
    scope = 'consum:online:zone-660:EUR'
    with catalogue.app_conn('test') as conn:
        conn.execute('RESET ROLE')
        conn.execute('UPDATE products SET source_metadata=%s WHERE id=%s',
                     (Jsonb({'price_context': scope}), identity))
        for price, context, hours in [(1, 'consum:online:zone-29:EUR', 2), (2, scope, 1)]:
            conn.execute('''INSERT INTO price_history(product_id,price,source_metadata,changed_at)
                VALUES(%s,%s,%s,now()-(%s * interval '1 hour'))''',
                (identity, price, Jsonb({'price_context': context}), hours))
        conn.execute('SET LOCAL ROLE app_user')
    product = http.get(f'/catalogue/products/{identity}').json()
    assert product['previous_price'] is None and product['change_percent'] is None
    history = http.get(f'/catalogue/products/{identity}/history').json()
    assert history['observation_count'] == 1
    assert [p['price'] for p in history['points']] == [2]


def test_summary_validation_and_unknown_product(client):
    http, prefix = client
    summary = http.get('/catalogue/summary').json()
    assert any(c['name'] == prefix and c['count'] == 4 for c in summary['categories'])
    assert summary['total'] >= 4
    for params in [{'page':0},{'page_size':101},{'sort':'name;DROP TABLE products'}, {'group_by':'unsafe'}, {'change':'unsafe'}]:
        assert http.get('/catalogue/products', params=params).status_code == 422
    assert http.get(f'/catalogue/products/{prefix}-single/history?days=0').status_code == 422
    assert http.get(f'/catalogue/products/{prefix}-missing').status_code == 404


def test_catalogue_requires_authentication():
    with TestClient(app) as http:
        for path in ['/catalogue/summary','/catalogue/products','/catalogue/products/missing','/catalogue/products/missing/history']:
            assert http.get(path).status_code in (401,403)
