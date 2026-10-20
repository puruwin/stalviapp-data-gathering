"""Disponibilidad provincial, precios por zona y snapshots sin duplicaciones."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pytest
import numpy as np

from api import catalogue, search
from api.tests.test_catalogue import dataset, client  # noqa: F401

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scraper'))
import regional_catalogue  # noqa: E402


def regional_dataset(prefix):
    with catalogue.app_conn('test') as conn:
        conn.execute('RESET ROLE')
        at = datetime.now(timezone.utc)-timedelta(hours=1)
        for zone,code,name in [('a','03','Alicante'),('b','03','Alicante'),('c','46','Valencia')]:
            zid=prefix+zone
            conn.execute('INSERT INTO catalogue_zones VALUES(%s,%s,%s,%s)',('mercadona',zid,name,at))
            conn.execute('INSERT INTO catalogue_zone_provinces VALUES(%s,%s,%s,%s,%s,%s)',
                         ('mercadona',zid,code,name,[code+'001'],'prueba'))
        for suffix,zone,price in [('down','a',5),('down','b',6),('up','c',8)]:
            pid=prefix+'-'+suffix
            conn.execute('INSERT INTO product_availability VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                         (pid,'mercadona',prefix+zone,price,price,'ud',True,at))
            conn.execute('''INSERT INTO regional_price_history(product_id,market,zone_id,price,changed_at)
                VALUES(%s,'mercadona',%s,%s,%s)''',(pid,prefix+zone,price,at))
        conn.execute('''INSERT INTO regional_price_history(product_id,market,zone_id,price,changed_at)
            VALUES(%s,'mercadona',%s,4,%s)''',(prefix+'-down',prefix+'a',at-timedelta(days=1)))
        conn.execute('SET LOCAL ROLE app_user')


def test_region_filters_deduplicate_and_use_local_price(client):
    http,prefix=client
    regional_dataset(prefix)
    data=http.get('/catalogue/products',params={'category':prefix,'province':'03'}).json()
    assert data['total']==1
    product=data['items'][0]
    assert product['id']==prefix+'-down'
    assert product['price']==5 and product['previous_price']==4
    assert product['price_scope']['province']=='Alicante'
    assert http.get('/catalogue/products/'+prefix+'-up',params={'province':'03'}).status_code==404
    assert http.get('/catalogue/products',params={'category':prefix,'province':'99'}).json()['total']==0
    summary=http.get('/catalogue/summary',params={'province':'03'}).json()
    assert next(c for c in summary['categories'] if c['name']==prefix)['count']==1
    assert any(p['code']=='03' for p in summary['provinces'])
    history=http.get('/catalogue/products/'+prefix+'-down/history',params={'province':'03'}).json()
    assert [p['price'] for p in history['points']]==[4,5]
    assert history['observation_count']==2
    assert http.get('/catalogue/summary',params={'province':'03 OR 1=1'}).status_code==422


def test_search_applies_province_before_limit_and_includes_unembedded_products(client,monkeypatch):
    http,prefix=client
    regional_dataset(prefix)
    monkeypatch.setattr(search,'app_conn',catalogue.app_conn)
    monkeypatch.setattr(search,'embed_query',lambda q:np.ones(384,dtype=np.float32))
    results=http.get('/search',params={'q':'Leche de prueba','province':'03','k':1}).json()
    assert len(results)==1 and results[0]['id']==prefix+'-down'
    assert results[0]['price']==5


def test_snapshot_is_idempotent_and_retires_missing_products_atomically(client,monkeypatch):
    _,prefix=client
    regional_dataset(prefix)
    at=datetime.now(timezone.utc)
    with catalogue.app_conn('test') as conn:
        conn.execute('RESET ROLE')
        @contextmanager
        def connection(*args,**kwargs):
            yield conn
        monkeypatch.setattr(regional_catalogue.psycopg,'connect',connection)
        monkeypatch.setattr(regional_catalogue.db,'get_dsn',lambda:'unused')
        zones=[{'zone_id':prefix+'a','label':'Zona prueba','observed_at':at}]
        provinces=[{'zone_id':prefix+'a','province_code':'03','province':'Alicante',
                    'postal_codes':['03001'],'evidence_kind':'prueba'}]
        rows=[{'product_id':prefix+'-down','zone_id':prefix+'a','price':5,'price_per_unit':5,
                'unit':'ud','observed_at':at}]
        first=regional_catalogue.import_snapshot('mercadona',zones,provinces,rows)
        second=regional_catalogue.import_snapshot('mercadona',zones,provinces,rows)
        assert first['history_added']==second['history_added']==0
        regional_catalogue.import_snapshot('mercadona',zones,provinces,[])
        assert conn.execute('SELECT available FROM product_availability WHERE product_id=%s AND zone_id=%s',
                            (prefix+'-down',prefix+'a')).fetchone()['available'] is False
        assert conn.execute('SELECT available FROM product_availability WHERE product_id=%s AND zone_id=%s',
                            (prefix+'-down',prefix+'b')).fetchone()['available'] is True
        conn.execute('SET LOCAL ROLE app_user')
