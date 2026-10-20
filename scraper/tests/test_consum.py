"""Contrato de Consum con respuestas reales y errores de paginación simulados."""

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from scrapers.consum import ConsumScraper
from scrapers.models import Category, RawProduct
from scrapers.validators import validate_product

FIXTURES = Path(__file__).parent / "fixtures" / "consum"
CATEGORY = Category("2076", "Entera", "Despensa > Lácteos y huevos > Leche", "")


def load(name):
    return json.loads((FIXTURES / name).read_text())


class FakeHTTP:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []
        self.delays = 0

    def get(self, url, **kwargs):
        self.urls.append(url)
        return next(self.responses)

    def delay(self):
        self.delays += 1


def item():
    result = copy.deepcopy(load("page-0.json")["products"][0])
    for offer in result["offers"]:
        offer["from"], offer["to"] = "2000-01-01T00:00:00Z", "2099-01-01T00:00:00Z"
    return result


def normalize(data):
    return ConsumScraper(FakeHTTP([])).normalize(RawProduct(str(data["code"]), data), CATEGORY)


def test_real_menu_keeps_full_path_and_only_leaves():
    menu = load("menu.json")
    menu.append({"id": 99999, "name": "Campaña", "type": 1})
    http = FakeHTTP([menu])
    scraper = ConsumScraper(http)
    categories = scraper.get_categories()
    assert {c.id for c in categories} == {"2076", "2156", "1294"}
    assert str(next(c for c in categories if c.id == "2076")) == "Despensa > Lácteos y huevos > Leche > Entera"
    assert scraper.get_categories() is categories
    assert len(http.urls) == 1
    # Aves incluye pollo y pavo: pendiente, sin inventar una equivalencia única.
    assert scraper.category_mapper.get_master_category(next(c for c in categories if c.id == "2156"), auto_map=False) is None


@pytest.mark.parametrize("response", [None, {}, {"result": {}}, [], [{"id": 1}]])
def test_invalid_menu_fails(response):
    with pytest.raises(RuntimeError):
        ConsumScraper(FakeHTTP([response])).get_categories()


def test_real_pages_advance_offset_and_deduplicate_overlap():
    first, second = load("page-0.json"), load("page-20.json")
    second["products"].insert(0, copy.deepcopy(first["products"][-1]))
    second.update(hasMore=False, totalCount=40)
    http = FakeHTTP([first, second])
    products = ConsumScraper(http).scrape_plp(CATEGORY)
    assert len(products) == 40
    assert len({p.raw_id for p in products}) == 40
    assert [parse_qs(urlsplit(url).query)["offset"] for url in http.urls] == [["0"], ["20"]]
    assert http.delays == 1
    assert products[0].raw_id == str(first["products"][0]["code"])


def test_limited_run_does_not_fetch_whole_category():
    http = FakeHTTP([load("page-0.json")])
    assert len(ConsumScraper(http, max_products_per_category=3).scrape_plp(CATEGORY)) == 3
    assert len(http.urls) == 1


@pytest.mark.parametrize("second", [None, {}, {"products": [], "hasMore": True, "totalCount": 3233}])
def test_failed_later_page_rejects_partial_category(second):
    with pytest.raises(RuntimeError):
        ConsumScraper(FakeHTTP([load("page-0.json"), second])).scrape_plp(CATEGORY)


def test_repeated_page_fails_instead_of_looping():
    page = load("page-0.json")
    with pytest.raises(RuntimeError, match="repetida"):
        ConsumScraper(FakeHTTP([page, page])).scrape_plp(CATEGORY)


def test_false_end_with_missing_products_fails():
    page = load("page-0.json")
    page["hasMore"] = False
    with pytest.raises(RuntimeError, match="truncado"):
        ConsumScraper(FakeHTTP([page])).scrape_plp(CATEGORY)


def test_empty_category_is_valid():
    assert ConsumScraper(FakeHTTP([{"products": [], "hasMore": False, "totalCount": 0}])).scrape_plp(CATEGORY) == []


def test_sponsored_duplicate_counts_toward_total_rows_not_unique_products():
    first, second = load("page-0.json"), load("page-20.json")
    second["products"][0] = copy.deepcopy(first["products"][0])
    second.update(hasMore=False, totalCount=40)
    products = ConsumScraper(FakeHTTP([first, second])).scrape_plp(CATEGORY)
    assert len(products) == 39


def test_gallery_preferred_over_broken_primary_image():
    data = item()
    product = normalize(data)
    assert product.image_url == data["media"][0]["url"]
    assert product.source_metadata["image_candidates"][0] == data["media"][0]["url"]
    assert data["productData"]["imageURL"] in product.source_metadata["image_candidates"]


def test_primary_image_used_when_no_gallery():
    data = item()
    data["media"] = []
    assert normalize(data).image_url == data["productData"]["imageURL"]


def test_immediate_offer_ean_and_metadata_survive_validation():
    data = item()
    product = validate_product(normalize(data))
    assert product.id == "consum_12542"
    assert product.price == 1.22
    assert product.price_per_unit == 1.22
    assert product.unit == "l"
    assert product.master_category_id == "lacteos.leche"
    assert product.source_metadata["ean"] == data["ean"]
    assert product.source_metadata["api_id"] == data["id"]
    assert product.source_metadata["price_data"]["prices"][0]["value"]["centAmount"] == 1.35
    assert product.source_metadata["price_context"] == ConsumScraper.PRICE_CONTEXT


@pytest.mark.parametrize("change", [
    {"inmediate": False}, {"promotionType": 2}, {"applicationTargetType": 2},
    {"applicationActionType": 1}, {"amount": 0.50}, {"to": "2000-01-02T00:00:00Z"},
    {"from": "2098-01-01T00:00:00Z"},
])
def test_conditional_or_expired_discount_does_not_lower_unit_price(change):
    data = item()
    data["offers"][0].update(change)
    product = normalize(data)
    assert product.price == 1.35
    assert product.source_metadata["selected_price_id"] == "PRICE"
    assert product.source_metadata["offers"] == data["offers"]


def test_offer_price_without_proven_immediate_offer_uses_base():
    data = item()
    data["offers"] = []
    assert normalize(data).price == 1.35


def test_replay_evaluates_promotions_at_observation_time():
    data = item()
    data['offers'][0].update({'from':'2026-10-19T00:00:00Z', 'to':'2026-10-21T00:00:00Z'})
    scraper = ConsumScraper(FakeHTTP([]))
    raw = RawProduct(str(data['code']), data)
    assert scraper.normalize(raw, CATEGORY, observed_at=datetime(2026,10,20,tzinfo=timezone.utc)).price == 1.22
    assert scraper.normalize(raw, CATEGORY, observed_at=datetime(2026,10,23,tzinfo=timezone.utc)).price == 1.35


def test_integer_euros_are_not_divided_by_100():
    data = item()
    data["offers"] = []
    data["priceData"]["prices"][0]["value"]["centAmount"] = 125
    assert normalize(data).price == 125


@pytest.mark.parametrize("amount", [None, -1, "NaN", "inf", 0])
def test_invalid_price_rejects_category(amount):
    data = item()
    data["offers"] = []
    data["priceData"]["prices"][0]["value"]["centAmount"] = amount
    with pytest.raises(ValueError):
        normalize(data)


@pytest.mark.parametrize("label,ppu,expected", [
    ("1 Kg", 6.95, ("kg", 6.95)), ("100 g", 1.25, ("kg", 12.5)),
    ("100 ml", 0.50, ("l", 5.0)), ("1 Unidad", 1.20, ("ud", 1.20)),
    ("1 Lv", 0.25, ("lavado", 0.25)),
])
def test_reference_units(label, ppu, expected):
    assert ConsumScraper._reference_unit(label, ppu) == expected


def test_stock_status_preserved_without_inventing_zero_price():
    data = item()
    data["productData"].update(availability="0", temporaryOutOfStock=True)
    product = normalize(data)
    assert product.price == 1.22
    assert product.source_metadata["availability"] == "0"
    assert product.source_metadata["temporary_out_of_stock"] is True


def test_partial_run_never_calls_database(monkeypatch, tmp_path):
    import db
    scraper = ConsumScraper(FakeHTTP([load("menu.json"), None, None, None]))
    monkeypatch.setattr(main, "get_scraper", lambda *a, **kw: scraper)
    monkeypatch.setattr(db, "upsert_products", lambda *a: pytest.fail("No debe persistir"))
    monkeypatch.setattr(db, "upsert_categories", lambda *a: pytest.fail("No debe persistir"))
    report = tmp_path / "report.json"
    with pytest.raises(RuntimeError, match="no se persiste"):
        main.run_scraper("consum", report=report)
    assert json.loads(report.read_text())["failed_categories"] == 3


def test_dry_run_deduplicates_without_writing_mappings(monkeypatch, tmp_path):
    page = load("page-0.json")
    page.update(hasMore=False, totalCount=20)
    scraper = ConsumScraper(FakeHTTP([load("menu.json"), page, page, page]))
    monkeypatch.setattr(main, "get_scraper", lambda *a, **kw: scraper)
    monkeypatch.setattr(scraper, "save_category_mappings", lambda: pytest.fail("Dry-run no escribe mapeos"))
    products = main.run_scraper("consum", dry_run=True, report=tmp_path / "report.json")
    assert len(products) == 20
    assert json.loads((tmp_path / "report.json").read_text())["persistence"] == "skipped"
