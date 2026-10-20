"""Unión reanudable de catálogos Mercadona y procedencia comprobada por CP.

El descubrimiento usa capitales peninsulares y municipios de Alicante. No se
equipara esta muestra con un censo de todos los centros ni con reparto universal.
Se pueden añadir CP a través de --postal-codes-file (uno por línea).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from consum_catalogue import write_json
from scrapers.mercadona import MercadonaScraper
from scrapers.models import Category, RawProduct
from scrapers.validators import validate_product

BASE = 'https://tienda.mercadona.es'
# Prefijos provinciales INE. Se excluyen islas, Ceuta y Melilla.
PROVINCES = dict(zip(
    '01 02 03 04 05 06 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 36 37 39 40 41 42 43 44 45 46 47 48 49 50'.split(),
    ['Álava','Albacete','Alicante','Almería','Ávila','Badajoz','Barcelona','Burgos','Cáceres','Cádiz','Castellón','Ciudad Real','Córdoba','A Coruña','Cuenca','Girona','Granada','Guadalajara','Gipuzkoa','Huelva','Huesca','Jaén','León','Lleida','La Rioja','Lugo','Madrid','Málaga','Murcia','Navarra','Ourense','Asturias','Palencia','Pontevedra','Salamanca','Cantabria','Segovia','Sevilla','Soria','Tarragona','Teruel','Toledo','Valencia','Valladolid','Bizkaia','Zamora','Zaragoza']))
DEFAULT_POSTALS = [p+'001' for p in PROVINCES] + [
    '03002','03003','03004','03005','03006','03007','03008','03009','03010','03011','03012','03013','03014','03015','03016',
    '03181','03182','03183','03184','03185','03186','03189','03201','03202','03203','03204','03205','03206',
    '03501','03502','03503','03540','03550','03600','03680','03700','03710','03801','03802','03803','03804','03300']


def session():
    http = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504], allowed_methods=['GET','PUT'])
    http.mount('https://', HTTPAdapter(max_retries=retry))
    http.headers['User-Agent'] = 'Stalviapp/0.1 (catalogue scraper)'
    return http


def discover(root, postals=None):
    path = root/'discovery.json'
    if path.exists():
        return json.loads(path.read_text())
    rows = []
    with session() as http:
        for postal in sorted(set(postals or DEFAULT_POSTALS)):
            if len(postal) != 5 or not postal.isdigit() or postal[:2] not in PROVINCES:
                raise ValueError(f'CP peninsular inválido: {postal}')
            response = http.put(BASE+'/api/postal-codes/actions/change-pc/', json={'new_postal_code':postal}, timeout=30)
            row = {'postal_code':postal,'province_code':postal[:2], 'province':PROVINCES[postal[:2]],
                   'status':response.status_code,'observed_at':datetime.now(timezone.utc).isoformat()}
            if response.status_code == 200:
                warehouse = response.headers.get('x-customer-wh')
                if not warehouse or response.headers.get('x-customer-pc') != postal:
                    raise RuntimeError(f'Asignación de almacén no verificable: {postal}')
                row['warehouse'] = warehouse
            elif response.status_code != 404:
                response.raise_for_status()
            rows.append(row)
            print('CP', postal, row.get('warehouse', 'sin cobertura'), flush=True)
            time.sleep(.15)
    write_json(path, rows)
    return rows


def collect_warehouse(root, warehouse):
    folder = root/'warehouses'/warehouse
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'report.json').exists():
        previous = json.loads((folder/'report.json').read_text())
        if previous['status'] == 'ok':
            return previous
    with session() as http:
        tree = http.get(BASE+'/api/categories/', params={'lang':'es','wh':warehouse}, timeout=30)
        tree.raise_for_status()
        data = tree.json()
        if data.get('next') or not data.get('results'):
            raise RuntimeError('Árbol vacío o paginación no resuelta')
        write_json(folder/'categories.json', data)
        categories = [{'id':str(c['id']),'name':c['name'],'parent_name':p['name']} for p in data['results']
                      for c in p.get('categories',[]) if c.get('published',True)]
        pages, seen, failed = [], set(), []
        for category in categories:
            path = folder/(category['id']+'.json.gz')
            try:
                if path.exists():
                    with gzip.open(path,'rt') as stream:
                        record = json.load(stream)
                else:
                    response = http.get(BASE+f"/api/categories/{category['id']}/", params={'lang':'es','wh':warehouse},timeout=30)
                    response.raise_for_status()
                    body = response.json()
                    if str(body.get('id')) != category['id'] or not isinstance(body.get('categories'),list):
                        raise RuntimeError('Categoría inesperada')
                    record = {'warehouse':warehouse,'category':category,'observed_at':datetime.now(timezone.utc).isoformat(),'data':body}
                    temporary = path.with_suffix('.tmp')
                    with gzip.open(temporary,'wt') as stream:
                        json.dump(record,stream,ensure_ascii=False)
                    temporary.replace(path)
                    time.sleep(.2)
                for child in record['data']['categories']:
                    for product in child.get('products',[]):
                        if not product.get('id'):
                            raise RuntimeError('Producto sin ID')
                        seen.add(str(product['id']))
                pages.append(str(path.relative_to(root)))
            except (RuntimeError, ValueError, OSError, requests.RequestException) as error:
                failed.append({'category':category['id'],'error':str(error)})
        result = {'warehouse':warehouse,'status':'failed' if failed else 'ok','categories':len(categories),
                  'unique_products':len(seen),'pages':pages,'failures':failed}
        if not seen:
            result['status'] = 'failed'
        write_json(folder/'report.json',result)
        return result


def collect(root, workers=4, postals=None):
    rows = discover(root, postals)
    warehouses = sorted({r['warehouse'] for r in rows if r.get('warehouse')})
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(collect_warehouse,root,wh) for wh in warehouses]):
            result = future.result()
            results.append(result)
            write_json(root/'progress.json',results)
            print(f"Almacén {result['warehouse']}: {result['status']}, {result['unique_products']} productos ({len(results)}/{len(warehouses)})",flush=True)
    if any(r['status'] != 'ok' for r in results):
        raise RuntimeError('Catálogo incompleto; reanudar antes de importar')
    return prepare(root, rows, results)


def prepare(root, rows, results):
    scraper = MercadonaScraper()
    chosen, observations, categories = {}, [], {}
    for result in sorted(results,key=lambda r:(r['warehouse']!='alc1',r['warehouse'])):
        wh = result['warehouse']
        for relative in result['pages']:
            with gzip.open(root/relative,'rt') as stream:
                record = json.load(stream)
            cat = record['category']
            category = Category(cat['id'],cat['name'],cat['parent_name'],cat['id'])
            categories[cat['id']] = {'market':'mercadona','external_id':cat['id'],'name':cat['name'],
                'parent_name':cat['parent_name'],'master_category_id':scraper.category_mapper.get_master_category(category)}
            for child in record['data']['categories']:
                for item in child.get('products',[]):
                    product = validate_product(scraper.normalize(RawProduct(str(item['id']),item),category))
                    if product is None:
                        raise RuntimeError(f"Producto inválido en {wh}: {item.get('id')}")
                    product.source_metadata = {'price_schema':'unit-price-v2','price_context':f'mercadona:online:{wh}:EUR:unit-price-v2',
                        'observed_at':record['observed_at'],'price_scope':{'zone_id':wh,'label':f'Precio online · almacén {wh}'}}
                    chosen.setdefault(product.id,product)
                    observations.append({'product_id':product.id,'zone_id':wh,'price':product.price,
                        'price_per_unit':product.price_per_unit,'unit':product.unit,'observed_at':record['observed_at'],
                        'available':item.get('published',True) and item.get('status') is None and item.get('limit',1)!=0})
    # Una aparición en varias categorías no constituye otra observación territorial.
    unique = {(r['product_id'],r['zone_id']):r for r in observations}
    write_json(root/'products.json',[p.to_dict() for p in chosen.values()])
    write_json(root/'categories.json',list(categories.values()))
    write_json(root/'regional-observations.json',list(unique.values()))
    report = {'unique_products':len(chosen),'warehouses':len(results),'warehouse_results':results,
        'postal_codes_tested':len(rows),'postal_codes_served':sum('warehouse' in r for r in rows),
        'scope':'Muestra de capitales peninsulares y municipios de Alicante; no es censo exhaustivo de almacenes.'}
    write_json(root/'catalogue-report.json',report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    parser.add_argument('--postal-codes-file',type=Path)
    args = parser.parse_args()
    postals = args.postal_codes_file.read_text().split() if args.postal_codes_file else None
    print(json.dumps(collect(args.root,args.workers,postals),ensure_ascii=False,indent=2))
