"""Persistencia transaccional de snapshots completos por zona y provincia."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import psycopg

import db
from mercadona_catalogue import PROVINCES
from scrapers.models import NormalizedProduct


def import_snapshot(market, zones, provinces, observations):
    """Sustituye solo las zonas incluidas; nunca borra productos ni otras zonas.

    El llamante debe haber validado la descarga completa. COPY a una tabla
    temporal evita cientos de miles de viajes de red. Histórico idempotente.
    """
    if not zones:
        raise ValueError('Snapshot sin zonas completas')
    if len({z['zone_id'] for z in zones}) != len(zones):
        raise ValueError('Zonas repetidas')
    with psycopg.connect(db.get_dsn()) as conn, conn.cursor() as cur:
        for z in zones:
            cur.execute('SELECT last_completed_at FROM catalogue_zones WHERE market=%s AND zone_id=%s FOR UPDATE',
                        (market,z['zone_id']))
            old = cur.fetchone()
            at = z['observed_at'] if isinstance(z['observed_at'],datetime) else datetime.fromisoformat(z['observed_at'])
            if old and at < (old['last_completed_at'] if isinstance(old,dict) else old[0]):
                raise ValueError('Snapshot anterior al cierre de zona ya importado')
        cur.executemany('''INSERT INTO catalogue_zones(market,zone_id,label,last_completed_at)
            VALUES(%s,%s,%s,%s) ON CONFLICT(market,zone_id) DO UPDATE
            SET label=excluded.label,last_completed_at=excluded.last_completed_at''',
            [(market,z['zone_id'],z['label'],z['observed_at']) for z in zones])
        zone_ids = [z['zone_id'] for z in zones]
        cur.execute('DELETE FROM catalogue_zone_provinces WHERE market=%s AND zone_id=ANY(%s)',(market,zone_ids))
        cur.executemany('''INSERT INTO catalogue_zone_provinces
            (market,zone_id,province_code,province,postal_codes,evidence_kind) VALUES(%s,%s,%s,%s,%s,%s)''',
            [(market,p['zone_id'],p['province_code'],p['province'],p['postal_codes'],p['evidence_kind']) for p in provinces])
        cur.execute('''CREATE TEMP TABLE incoming_availability (
            product_id TEXT, market TEXT, zone_id TEXT, price NUMERIC(10,2),
            price_per_unit NUMERIC(12,4), unit TEXT, available BOOLEAN, observed_at TIMESTAMPTZ,
            PRIMARY KEY(product_id,market,zone_id)) ON COMMIT DROP''')
        count = 0
        with cur.copy('COPY incoming_availability FROM STDIN') as copy:
            for row in observations:
                if row['zone_id'] not in zone_ids:
                    raise ValueError('Observación fuera de las zonas completas')
                copy.write_row((row['product_id'],market,row['zone_id'],row['price'],row['price_per_unit'],
                                row['unit'],row.get('available',True),row['observed_at']))
                count += 1
        cur.execute('''SELECT 1 FROM incoming_availability i LEFT JOIN products p
            ON p.id=i.product_id AND p.supermarket=i.market WHERE p.id IS NULL LIMIT 1''')
        if cur.fetchone():
            raise ValueError('Producto desconocido o de otra cadena')
        cur.execute('''SELECT 1 FROM incoming_availability i JOIN catalogue_zones z
            ON z.market=i.market AND z.zone_id=i.zone_id
            WHERE i.observed_at > z.last_completed_at LIMIT 1''')
        if cur.fetchone():
            raise ValueError('Observación posterior al cierre del snapshot')
        # No reemplazar una observación más reciente con un checkpoint antiguo.
        cur.execute('''SELECT 1 FROM incoming_availability i JOIN product_availability a
            USING(product_id,market,zone_id) WHERE i.observed_at < a.observed_at LIMIT 1''')
        if cur.fetchone():
            raise ValueError('Snapshot anterior a los datos ya importados')
        cur.execute('''INSERT INTO regional_price_history(product_id,market,zone_id,price,price_per_unit,changed_at)
            SELECT i.product_id,i.market,i.zone_id,i.price,i.price_per_unit,i.observed_at
            FROM incoming_availability i LEFT JOIN product_availability a USING(product_id,market,zone_id)
            WHERE a.product_id IS NULL OR i.price IS DISTINCT FROM a.price
              OR i.price_per_unit IS DISTINCT FROM a.price_per_unit''')
        history = cur.rowcount
        cur.execute('''UPDATE product_availability a SET available=false
            WHERE a.market=%s AND a.zone_id=ANY(%s) AND a.available
              AND NOT EXISTS (SELECT 1 FROM incoming_availability i
                WHERE i.product_id=a.product_id AND i.market=a.market AND i.zone_id=a.zone_id)''',(market,zone_ids))
        removed = cur.rowcount
        cur.execute('''INSERT INTO product_availability SELECT * FROM incoming_availability
            ON CONFLICT(product_id,market,zone_id) DO UPDATE SET
            price=excluded.price,price_per_unit=excluded.price_per_unit,unit=excluded.unit,
            available=excluded.available,observed_at=excluded.observed_at''')
        cur.execute('DROP TABLE incoming_availability')
    return {'market':market,'zones':len(zones),'observations':count,'history_added':history,'no_longer_available':removed}


def import_consum(root):
    report = json.loads((root/'collection-report.json').read_text())
    if report['failed_zones']:
        raise ValueError('Consum: descarga incompleta')
    raw = json.loads((root/'zones.json').read_text())
    zones, provinces = [], []
    for z in raw:
        if z['zone_id']=='0':
            continue
        zone_report = json.loads((root/'zones'/z['zone_id']/'report.json').read_text())
        if zone_report['status'] not in ('ok','empty'):
            raise ValueError('Zona Consum incompleta')
        code = z['zip_code'][:2]
        zones.append({'zone_id':z['zone_id'],'label':f"Consum · {z['city']}, {PROVINCES[code]}",
                      'observed_at':zone_report['finished_at']})
        provinces.append({'zone_id':z['zone_id'],'province_code':code,'province':PROVINCES[code],
                          'postal_codes':[z['zip_code']],'evidence_kind':'centro_publicado_en_provincia'})
    raw_observations = json.loads((root/'regional-observations.json').read_text())
    observations = ({**o,'product_id':'consum_'+sku} for sku,by_zone in raw_observations.items()
                    for zone,o in by_zone.items() if zone!='0')
    return import_snapshot('consum',zones,provinces,observations)


def import_mercadona(root):
    report = json.loads((root/'catalogue-report.json').read_text())
    if any(r['status']!='ok' for r in report['warehouse_results']):
        raise ValueError('Mercadona: descarga incompleta')
    products = [NormalizedProduct(**p) for p in json.loads((root/'products.json').read_text())]
    product_stats = db.upsert_products(products)
    db.upsert_categories(json.loads((root/'categories.json').read_text()))
    observations = json.loads((root/'regional-observations.json').read_text())
    observed = {}
    for o in observations:
        observed[o['zone_id']] = max(observed.get(o['zone_id'],''),o['observed_at'])
    zones = [{'zone_id':wh,'label':f'Mercadona · almacén {wh}','observed_at':at} for wh,at in observed.items()]
    provinces = {}
    for row in json.loads((root/'discovery.json').read_text()):
        if not row.get('warehouse'):
            continue
        key = (row['warehouse'],row['province_code'])
        entry = provinces.setdefault(key,{'zone_id':row['warehouse'],'province_code':row['province_code'],
            'province':row['province'],'postal_codes':[],'evidence_kind':'asignacion_almacen_por_codigo_postal'})
        entry['postal_codes'].append(row['postal_code'])
    return {**import_snapshot('mercadona',zones,list(provinces.values()),observations),'products':product_stats}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('market',choices=['consum','mercadona'])
    parser.add_argument('root',type=Path)
    args = parser.parse_args()
    result = import_consum(args.root) if args.market=='consum' else import_mercadona(args.root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
