"""Unión por SKU, asignación territorial y rechazo de capturas incompletas."""
import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mercadona_catalogue as catalogue


def test_union_deduplicates_categories_and_warehouses(tmp_path):
    def item(pid,price):
        return {'id':pid,'display_name':'Producto '+pid,'published':True,'status':None,
                'price_instructions':{'bulk_price':price,'unit_price':price,'reference_format':'ud'}}
    reports=[]
    for wh,price in [('alc1','1.20'),('vlc1','1.50')]:
        path=tmp_path/(wh+'.json.gz')
        record={'category':{'id':'112','name':'Aceite','parent_name':'Despensa'},
                'observed_at':'2026-10-20T10:00:00+00:00','data':{'categories':[
                    {'products':[item('1',price)]},{'products':[item('1',price)]}]}}
        with gzip.open(path,'wt') as f:json.dump(record,f)
        reports.append({'warehouse':wh,'status':'ok','pages':[path.name]})
    result=catalogue.prepare(tmp_path,[],reports)
    assert result['unique_products']==1
    products=json.loads((tmp_path/'products.json').read_text())
    assert products[0]['id']=='mercadona_1' and products[0]['price']==1.2
    observations=json.loads((tmp_path/'regional-observations.json').read_text())
    assert len(observations)==2
    assert {r['price'] for r in observations}=={1.2,1.5}


def test_postal_code_requires_matching_assignment_headers(monkeypatch,tmp_path):
    class Response:
        status_code=200
        headers={'x-customer-wh':'vlc1','x-customer-pc':'46001'}
    class HTTP:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def put(self,*args,**kwargs):return Response()
    monkeypatch.setattr(catalogue,'session',HTTP)
    with pytest.raises(RuntimeError,match='no verificable'):
        catalogue.discover(tmp_path,['03001'])
    assert not (tmp_path/'discovery.json').exists()


def test_incomplete_warehouse_blocks_preparation(monkeypatch,tmp_path):
    monkeypatch.setattr(catalogue,'discover',lambda *args:[{'warehouse':'alc1'}])
    monkeypatch.setattr(catalogue,'collect_warehouse',lambda *args:{'warehouse':'alc1','status':'failed','unique_products':0})
    with pytest.raises(RuntimeError,match='incompleto'):
        catalogue.collect(tmp_path,workers=1)
    assert not (tmp_path/'products.json').exists()


def test_mercadona_separates_package_price_from_reference_price():
    from scrapers.mercadona import MercadonaScraper
    from scrapers.models import Category,RawProduct
    product=MercadonaScraper().normalize(RawProduct('4241',{
        'display_name':'Aceite de oliva 0,4º Hacendado',
        'price_instructions':{'unit_price':'17.25','bulk_price':'3.45',
                              'reference_price':'3.450','reference_format':'L'}}),
        Category('112','Aceite','Despensa','112'))
    assert product.price==17.25
    assert product.price_per_unit==3.45 and product.unit=='L'
    assert product.source_metadata['price_schema']=='unit-price-v2'
