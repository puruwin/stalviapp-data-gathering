"""Catálogo unificado de las zonas reales publicadas por Consum.

Cada ejecución usa su propio directorio de evidencia. Los precios de referencia
conservan el ámbito original; el histórico nunca mezcla observaciones regionales.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import logging
from pathlib import Path
import threading
import time
from urllib.parse import urlencode, urlsplit

import requests

from scrapers.consum import ConsumScraper
from scrapers.http_client import HttpClient
from scrapers.models import Category, NormalizedProduct, RawProduct
from scrapers.validators import validate_product

BASE = ConsumScraper.BASE_URL


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def real_zones(groups):
    """Una entrada por centro real; las rutas de reparto se conservan juntas."""
    if not isinstance(groups, list) or not groups:
        raise ValueError('Consum: listado de zonas inválido')
    zones = {}
    for group in groups:
        for area in group.get('shippingAreas', []):
            zone = area.get('zone') or {}
            address = zone.get('address') or {}
            identity = str(zone.get('id', ''))
            name = zone.get('name', '')
            postal = str(address.get('zipCode', ''))
            if (not area.get('enabled') or area.get('deliveryTypeId') != 'D'
                    or not identity.isdigit() or identity == '0'
                    or not postal.isdigit() or len(postal) != 5
                    or any(word in name.lower() for word in ('test', 'prueba'))):
                continue
            row = zones.setdefault(identity, {
                'zone_id': identity, 'shipping_zone_ids': [], 'name': name,
                'province': group.get('groupName'), 'zip_code': postal,
                'city': address.get('city'),
            })
            if area.get('shippingZoneId') not in row['shipping_zone_ids']:
                row['shipping_zone_ids'].append(area['shippingZoneId'])
    if not zones:
        raise ValueError('Consum: no se encontraron zonas reales')
    return list(zones.values())


def discover(root):
    http = HttpClient(headers={'User-Agent': 'Stalviapp/0.1 (catalogue scraper)'})
    url = BASE + '/api/rest/V1.0/shipping/area?' + urlencode({
        'shippingMethod': 'D,X,T,L', 'showDisableStore': 'false',
    })
    data = http.get(url)
    zones = real_zones(data)
    write_json(root / 'shipping-areas.json', data)
    # El catálogo anónimo es un control adicional, no una zona geográfica real.
    zones.insert(0, {'zone_id': '0', 'shipping_zone_ids': ['0D'], 'name': 'Catálogo anónimo',
                     'province': None, 'zip_code': None, 'city': None})
    write_json(root / 'zones.json', zones)
    return zones


def collect_zone(root, zone):
    folder = root / 'zones' / zone['zone_id']
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / 'report.json'
    if report.exists():
        previous = json.loads(report.read_text())
        if previous.get('status') in ('ok', 'empty'):
            return previous
    attempts = []
    # Una ordenación alternativa permite recuperar una página defectuosa sin
    # aceptar silenciosamente un catálogo truncado ni tocar la evidencia previa.
    routes = [(shipping, order_by) for order_by in (3, 1) for shipping in zone['shipping_zone_ids']]
    for shipping, order_by in routes:
        http = HttpClient(base_delay=1, headers={
            'User-Agent': 'Stalviapp/0.1 (catalogue scraper)', 'X-TOL-LOCALE': 'es',
            'X-TOL-CHANNEL': '1', 'X-TOL-CURRENCY': 'EUR', 'X-TOL-ZONE': zone['zone_id'],
            'X-TOL-SHIPPING-ZONE': shipping,
        })
        cache_name = hashlib.sha256(shipping.encode()).hexdigest()[:12]
        target = folder / (cache_name if order_by == 3 else cache_name + f'-order{order_by}')
        target.mkdir(exist_ok=True)
        offset, seen, pages, totals = 0, set(), [], []
        started = datetime.now(timezone.utc).isoformat()
        try:
            for _ in range(1000):
                path = target / f'{offset:06d}.json.gz'
                cached = path.exists()
                if cached:
                    try:
                        with gzip.open(path, 'rt') as stream:
                            record = json.load(stream)
                        data = record['data']
                    except (OSError, EOFError, ValueError, KeyError):
                        path.replace(path.with_suffix(path.suffix + '.corrupt'))
                        cached = False
                if not cached:
                    url = BASE + '/api/rest/V1.0/catalog/product?' + urlencode({
                        'offset': offset, 'limit': 100, 'orderById': order_by,
                        'showProducts': 'true', 'showRecommendations': 'false',
                    })
                    data = http.get(url)
                    if not isinstance(data, dict):
                        raise RuntimeError(f'Descarga fallida offset={offset}')
                    record = {'url': url, 'zone_id': zone['zone_id'], 'shipping_zone_id': shipping,
                              'observed_at': datetime.now(timezone.utc).isoformat(), 'data': data}
                    if isinstance(data.get('products'), list):
                        temporary = path.with_suffix(path.suffix + '.tmp')
                        with gzip.open(temporary, 'wt') as stream:
                            json.dump(record, stream, ensure_ascii=False)
                        temporary.replace(path)
                items, more, total = data.get('products'), data.get('hasMore'), data.get('totalCount')
                if not isinstance(items, list) or type(more) is not bool or type(total) is not int:
                    raise RuntimeError('Paginación inválida')
                before = len(seen)
                for item in items:
                    if not item.get('code') or item.get('id') is None:
                        raise RuntimeError('Producto sin SKU/ID')
                    seen.add(str(item['code']))
                if items and len(seen) == before:
                    raise RuntimeError('Página repetida')
                totals.append(total)
                pages.append(str(path.relative_to(root)))
                offset += len(items)
                if not more:
                    if offset < total:
                        raise RuntimeError(f'Filas insuficientes {offset}/{total}')
                    break
                if not items:
                    raise RuntimeError('Página vacía con continuación')
                if not cached:
                    http.delay()
            else:
                raise RuntimeError('Límite de páginas excedido')
            result = {'zone': zone, 'shipping_zone_id': shipping, 'status': 'ok' if seen else 'empty',
                      'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
                      'unique_products': len(seen), 'raw_rows': offset, 'totals': sorted(set(totals)),
                      'pages': pages, 'attempts': list(attempts)}
            if not seen:
                attempts.append({'shipping_zone_id': shipping, 'status': 'empty'})
                if shipping != zone['shipping_zone_ids'][-1]:
                    continue
            write_json(report, result)
            return result
        except Exception as error:
            attempts.append({'shipping_zone_id': shipping, 'order_by': order_by, 'status': 'failed', 'error': str(error)})
            result = {'zone': zone, 'status': 'failed', 'error': str(error), 'pages': pages, 'attempts': attempts}
            write_json(report, result)
            if order_by == 3 and ('Página repetida' in str(error) or 'Filas insuficientes' in str(error)):
                continue
            return result
    raise RuntimeError('Zona sin rutas de reparto')


def collect(root, workers=4):
    zones_path = root / 'zones.json'
    zones = json.loads(zones_path.read_text()) if zones_path.exists() else discover(root)
    results = []
    started = datetime.now(timezone.utc).isoformat()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(collect_zone, root, zone) for zone in zones]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            report = {'started_at': started, 'updated_at': datetime.now(timezone.utc).isoformat(),
                      'total_zones': len(zones), 'completed_zones': len(results),
                      'failed_zones': sum(r['status'] == 'failed' for r in results), 'results': results}
            write_json(root / 'progress.json', report)
            print(f"[{len(results)}/{len(zones)}] {row['zone']['zone_id']} {row['status']} {row.get('unique_products', 0)}", flush=True)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_json(root / 'collection-report.json', report)
    return report


def reference_priority(zone_id):
    """Orden estable de selección; cada precio guarda su ámbito explícito."""
    return (zone_id != '0', int(zone_id))


def prepare(root):
    zones = json.loads((root / 'zones.json').read_text())
    reports = []
    for zone in zones:
        path = root / 'zones' / zone['zone_id'] / 'report.json'
        if not path.exists():
            raise RuntimeError(f"Zona todavía sin completar: {zone['zone_id']}")
        report = json.loads(path.read_text())
        if zone['zone_id'] != '0' and report['status'] == 'failed':
            raise RuntimeError(f"Zona fallida: {zone['zone_id']}. Reanudar antes de importar.")
        reports.append(report)
    scraper = ConsumScraper()
    categories = {c.id: c for c in scraper.get_categories()}
    chosen, observations, rejected = {}, {}, []
    for report in sorted(reports, key=lambda r: reference_priority(r['zone']['zone_id'])):
        zone = report['zone']
        zone_id = zone['zone_id']
        # Los datos parciales del control anónimo son observaciones válidas de
        # precio; no se contabilizan como cobertura de una zona real.
        for relative in report.get('pages', []):
            with gzip.open(root / relative, 'rt') as stream:
                record = json.load(stream)
            for item in record['data']['products']:
                code = str(item['code'])
                original = [categories[str(c['id'])] for c in item.get('categories', []) if str(c['id']) in categories]
                if original:
                    category = max(original, key=lambda c: c.parent_name.count(' > '))
                else:
                    raw_category = next((c for c in item.get('categories', []) if c.get('type', 0) == 0), {})
                    category = Category(str(raw_category.get('id', 'unlisted')), raw_category.get('name', 'Sin categoría publicada'), 'Consum', '')
                context = (ConsumScraper.PRICE_CONTEXT if zone_id == '0'
                           else f'consum:online:zone-{zone_id}:EUR')
                scraper.price_context = context
                try:
                    product = validate_product(scraper.normalize(
                        RawProduct(code, item), category,
                        observed_at=datetime.fromisoformat(record['observed_at'])))
                    if product is None:
                        raise ValueError('Producto no válido')
                except (ValueError, TypeError, KeyError) as error:
                    rejected.append({'zone_id': zone_id, 'sku': code, 'error': str(error)})
                    continue
                product.source_metadata['observed_at'] = record['observed_at']
                product.source_metadata['price_scope'] = {
                    'zone_id': zone_id, 'shipping_zone_id': record['shipping_zone_id'],
                    'province': zone.get('province'), 'city': zone.get('city'),
                    'label': ('Precio online de referencia · sin zona seleccionada' if zone_id == '0'
                              else f"Precio online de referencia · {zone.get('city')}, {zone.get('province', '').title()}"),
                }
                chosen.setdefault(code, product)
                observations.setdefault(code, {})[zone_id] = {
                    'zone_id': zone_id, 'province': zone.get('province'),
                    'price': product.price, 'price_per_unit': product.price_per_unit, 'unit': product.unit,
                    'observed_at': record['observed_at'],
                }
    if rejected:
        write_json(root / 'normalization-errors.json', rejected)
        raise RuntimeError(f'{len(rejected)} observaciones inválidas; revisar antes de importar')
    for code, product in chosen.items():
        regional = [o for o in observations[code].values() if o['zone_id'] != '0']
        unit_prices = {(o['unit'], o['price_per_unit']) for o in regional if o['price_per_unit'] is not None}
        product.source_metadata['coverage'] = {
            'zone_ids': sorted([o['zone_id'] for o in regional], key=int),
            'provinces': sorted({o['province'] for o in regional if o['province']}),
            'zones_observed': len(regional),
            'unit_price_variants': len(unit_prices),
        }
    write_json(root / 'products.json', [p.to_dict() for p in chosen.values()])
    write_json(root / 'categories.json', [{
        'market': 'consum', 'external_id': c.id, 'name': c.name, 'parent_name': c.parent_name,
        'master_category_id': scraper.category_mapper.get_master_category(c, auto_map=False),
    } for c in categories.values()])
    write_json(root / 'regional-observations.json', observations)
    summary = {'unique_products': len(chosen), 'real_zones': len(zones) - 1,
               'zones_with_catalogue': sum(r['zone']['zone_id'] != '0' and r['status'] == 'ok' for r in reports),
               'empty_zones': [r['zone']['zone_id'] for r in reports if r['status'] == 'empty'],
               'anonymous_control_status': next(r['status'] for r in reports if r['zone']['zone_id'] == '0'),
               'provinces': sorted({z['province'] for z in zones if z.get('province')}),
               'products_with_multiple_unit_prices': sum(p.source_metadata['coverage']['unit_price_variants'] > 1 for p in chosen.values())}
    write_json(root / 'catalogue-report.json', summary)
    return summary


def import_products(root):
    import db
    # El archivo de productos solo se prepara cuando la cobertura regional es completa.
    if not (root / 'catalogue-report.json').exists():
        raise RuntimeError('Preparar y validar el catálogo antes de importar')
    products = json.loads((root / 'products.json').read_text())
    audit_path = root / 'image-audit.json'
    if audit_path.exists():
        images = json.loads(audit_path.read_text())
        for product in products:
            result = images.get(product['id'], {})
            if result.get('url'):
                product['image_url'] = result['url']
                product['source_metadata']['image_verified_at'] = result['checked_at']
            elif result.get('status') == 'missing':
                product['image_url'] = ''
                product['source_metadata']['original_image_candidates'] = product['source_metadata'].get('image_candidates', [])
                product['source_metadata']['image_candidates'] = []
            product['source_metadata']['image_status'] = result.get('status', 'not_checked')
    normalized = [NormalizedProduct(**p) for p in products]
    categories = json.loads((root / 'categories.json').read_text())
    db.upsert_categories(categories)
    stats = db.upsert_products(normalized)
    mapper = ConsumScraper().category_mapper
    for row in categories:
        mapper.register_pending(Category(row['external_id'], row['name'], row['parent_name'], ''))
    mapper.save_mappings()
    write_json(root / 'import-report.json', {'imported_at': datetime.now(timezone.utc).isoformat(), **stats})
    return stats


def audit_images(root, workers=4):
    """Verifica el CDN por HEAD, sin descargar ni fabricar fotografías."""
    products = json.loads((root / 'products.json').read_text())
    cache = root / 'image-checks'
    cache.mkdir(exist_ok=True)
    local = threading.local()

    def check(product):
        identity = product['id']
        path = cache / (hashlib.sha256(identity.encode()).hexdigest() + '.json')
        # Aceptar también los checkpoints legibles del primer sondeo.
        legacy = cache / (identity + '.json')
        previous = path if path.exists() else legacy
        if previous.exists():
            return identity, json.loads(previous.read_text())
        if not hasattr(local, 'session'):
            local.session = requests.Session()
            local.session.headers['User-Agent'] = 'Stalviapp/0.1 (product image verification)'
        urls = list(dict.fromkeys([product['image_url'], *product['source_metadata'].get('image_candidates', [])]))
        if len(urls) == 1 and urls[0]:
            base = urls[0].split('?')[0]
            if base.endswith('.jpg') and not base.endswith('_001.jpg'):
                urls.insert(0, base[:-4] + '_001.jpg')
        attempts, selected = [], None
        for candidate in urls:
            parsed = urlsplit(candidate)
            if parsed.scheme != 'https' or parsed.hostname != 'cdn-consum.aktiosdigitalservices.com':
                continue
            try:
                response = local.session.head(candidate, timeout=15, allow_redirects=False)
                attempts.append({'url': candidate, 'status': response.status_code,
                                 'content_type': response.headers.get('Content-Type')})
                if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/'):
                    selected = candidate
                    break
            except requests.RequestException as error:
                attempts.append({'url': candidate, 'error': str(error)})
            time.sleep(.1)
        uncertain = any(a.get('error') or a.get('status', 0) in (429, 500, 502, 503, 504) for a in attempts)
        result = {'status': 'ok' if selected else 'error' if uncertain else 'missing',
                  'url': selected, 'checked_at': datetime.now(timezone.utc).isoformat(), 'attempts': attempts}
        write_json(path, result)
        time.sleep(.1)
        return identity, result

    results = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(check, p) for p in products]):
            identity, result = future.result()
            results[identity] = result
            if len(results) % 500 == 0:
                print(f'Imágenes verificadas: {len(results)}/{len(products)}', flush=True)
    write_json(root / 'image-audit.json', results)
    summary = {'products': len(products), 'ok': sum(r['status'] == 'ok' for r in results.values()),
               'missing': [identity for identity, r in results.items() if r['status'] == 'missing'],
               'errors': [identity for identity, r in results.items() if r['status'] == 'error']}
    write_json(root / 'image-audit-report.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('discover', 'collect', 'prepare', 'images', 'import'))
    parser.add_argument('--work-dir', type=Path, required=True, help='Directorio propio de esta observación; reutilizar solo para reanudarla')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    root = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    action = {'discover': discover, 'collect': lambda r: collect(r, args.workers),
              'prepare': prepare, 'images': lambda r: audit_images(r, args.workers),
              'import': import_products}[args.action]
    result = action(root)
    if isinstance(result, dict):
        result = {k: v for k, v in result.items() if k != 'results'}
    elif isinstance(result, list):
        result = {'zones': len(result)}
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
