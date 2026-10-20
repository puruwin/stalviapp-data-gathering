"""Unificación y cobertura regional con snapshots aislados, sin red."""
import copy
import gzip
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from consum_catalogue import prepare, real_zones, reference_priority, collect_zone
from scrapers.consum import ConsumScraper
from scrapers.models import Category


def test_real_zones_excludes_test_records_and_deduplicates_centres():
    def area(identity, name, postal, shipping):
        return {'enabled': True, 'deliveryTypeId': 'D', 'shippingZoneId': shipping,
                'zone': {'id': identity, 'name': name, 'address': {'zipCode': postal, 'city': 'Valencia'}}}
    groups = [{'groupName': 'VALENCIA', 'shippingAreas': [
        area(660, 'Centro 660', '46001', '660D'), area(660, 'Centro 660', '46001', '660D2'),
        area(99999, 'Zona test 99999', '50008', '99999D'), area(1111, 'prueba', '1', '1111D'),
        area(0, 'Zona 0', '46001', '0D'),
    ]}]
    zones = real_zones(groups)
    assert len(zones) == 1
    assert zones[0]['zone_id'] == '660'
    assert zones[0]['shipping_zone_ids'] == ['660D', '660D2']


def test_reference_priority_is_stable():
    assert sorted(['660', '0', '29'], key=reference_priority) == ['0', '29', '660']


def test_unification_preserves_reference_scope_and_does_not_duplicate(monkeypatch, tmp_path):
    fixture = json.loads((Path(__file__).parent / 'fixtures/consum/page-0.json').read_text())['products'][0]
    monkeypatch.setattr(ConsumScraper, 'get_categories', lambda self: [Category('2076', 'Entera', 'Leche', '')])
    zones = [{'zone_id': identity, 'shipping_zone_ids': [identity+'D'], 'province': province, 'city': 'Ciudad'}
             for identity, province in [('0', None), ('660', 'ALBACETE')]]
    (tmp_path/'zones.json').write_text(json.dumps(zones))
    for zone in zones:
        folder = tmp_path/'zones'/zone['zone_id']
        folder.mkdir(parents=True)
        item = copy.deepcopy(fixture)
        item['offers'] = []
        item['priceData']['prices'] = [item['priceData']['prices'][0]]
        if zone['zone_id'] == '660':
            item['priceData']['prices'][0]['value']['centAmount'] = 2
        page = folder/'page.json.gz'
        with gzip.open(page, 'wt') as stream:
            json.dump({'shipping_zone_id':zone['zone_id']+'D', 'observed_at':'2026-10-20T12:00:00+00:00',
                       'data':{'products':[item]}}, stream)
        (folder/'report.json').write_text(json.dumps({'zone':zone, 'status':'ok', 'pages':[str(page.relative_to(tmp_path))]}))
    result = prepare(tmp_path)
    assert result['unique_products'] == 1 and result['zones_with_catalogue'] == 1
    products = json.loads((tmp_path/'products.json').read_text())
    product = products[0]
    assert product['price'] == 1.35
    assert product['source_metadata']['price_context'] == ConsumScraper.PRICE_CONTEXT
    assert product['source_metadata']['observed_at'] == '2026-10-20T12:00:00+00:00'
    assert product['source_metadata']['coverage']['zone_ids'] == ['660']


def test_incomplete_zone_blocks_preparation(tmp_path):
    zones = [{'zone_id':'0'}, {'zone_id':'660'}]
    (tmp_path/'zones.json').write_text(json.dumps(zones))
    folder = tmp_path/'zones/0'
    folder.mkdir(parents=True)
    (folder/'report.json').write_text(json.dumps({'zone':zones[0], 'status':'failed', 'pages':[]}))
    with pytest.raises(RuntimeError, match='sin completar'):
        prepare(tmp_path)


def test_corrupt_checkpoint_is_refetched_then_reused(monkeypatch, tmp_path):
    import hashlib
    import consum_catalogue
    zone = {'zone_id':'660','shipping_zone_ids':['660D'],'province':'ALBACETE','city':'Almansa'}
    folder = tmp_path/'zones/660'/hashlib.sha256(b'660D').hexdigest()[:12]
    folder.mkdir(parents=True)
    (folder/'000000.json.gz').write_bytes(b'Interrumpido')
    calls = []
    class HTTP:
        def __init__(self, **kwargs): pass
        def get(self, url):
            calls.append(url)
            return {'products':[], 'hasMore':False, 'totalCount':0}
        def delay(self): pass
    monkeypatch.setattr(consum_catalogue, 'HttpClient', HTTP)
    assert collect_zone(tmp_path, zone)['status'] == 'empty'
    assert len(calls) == 1
    assert (folder/'000000.json.gz.corrupt').exists()
    assert collect_zone(tmp_path, zone)['status'] == 'empty'
    assert len(calls) == 1


def test_repeated_page_retries_with_separate_ordering_checkpoint(monkeypatch, tmp_path):
    import consum_catalogue
    from urllib.parse import parse_qs, urlsplit
    item = json.loads((Path(__file__).parent/'fixtures/consum/page-0.json').read_text())['products'][0]
    repeated = {'products':[item], 'hasMore':True, 'totalCount':2}
    recovered = {'products':[item], 'hasMore':False, 'totalCount':1}
    responses = iter([repeated, repeated, recovered])
    calls = []
    class HTTP:
        def __init__(self, **kwargs): pass
        def get(self, url):
            calls.append(parse_qs(urlsplit(url).query))
            return next(responses)
        def delay(self): pass
    monkeypatch.setattr(consum_catalogue, 'HttpClient', HTTP)
    report = collect_zone(tmp_path, {'zone_id':'660','shipping_zone_ids':['660D']})
    assert report['status'] == 'ok'
    assert [c['orderById'] for c in calls] == [['3'], ['3'], ['1']]
    assert '-order1/' in report['pages'][0]
