from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from prozorro_history.normalize import Lot, extract_area, normalize, ua

LoadFixture = Callable[[str], dict[str, Any]]


def make_lot(**overrides: Any) -> Lot:
    values: dict[str, Any] = {
        "procedure_id": "p1",
        "auction_id": "a1",
        "previous_auction_id": None,
        "tender_attempts": None,
        "status": "unsuccessful",
        "selling_method": "commercialSell-english",
        "date_modified": "2026-11-01T00:00:00Z",
        "title": None,
        "start_price": None,
        "currency": None,
        "cav_code": None,
        "region": None,
        "locality": None,
        "area_m2": None,
        "land_area_ha": None,
        "auction_date": None,
        "source_url": "https://prozorro.sale/auction/a1/",
        "api_url": "https://procedure.prozorro.sale/api/search/byAuctionId/a1",
    }
    values.update(overrides)
    return Lot(**values)


def test_fixture_loads(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    assert raw["auctionId"] == "CSE001-UA-20261003-41261"


def test_lot_is_frozen() -> None:
    lot = make_lot()
    with pytest.raises(FrozenInstanceError):
        # Deliberate violation: mypy rightly rejects it, pytest.raises proves
        # it also fails at runtime (i.e. frozen=True is really on).
        lot.status = "complete"  # type: ignore[misc]


def test_ua_none_returns_none() -> None:
    assert ua(None) is None


def test_ua_prefers_ukrainian() -> None:
    assert ua({"uk_UA": "Київ", "en_US": "Kyiv"}) == "Київ"


def test_ua_falls_back_to_english() -> None:
    assert ua({"en_US": "Kyiv"}) == "Kyiv"


def test_ua_empty_dict_returns_none() -> None:
    assert ua({}) is None


def test_ua_on_real_title(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    title = ua(raw["title"])
    assert title is not None
    assert title.startswith("Продаж нерухомого майна")


def test_area_item_props_beats_mtk_quantity() -> None:
    item = {
        "unit": {"code": "MTK"},
        "quantity": 1,
        "itemProps": {"totalObjectArea": 1893.2},
    }
    assert extract_area(item) == (1893.2, None)


def test_area_item_props_with_any_unit() -> None:
    item = {
        "unit": {"code": "LO"},
        "quantity": 118.0,
        "itemProps": {"totalObjectArea": 118.0},
    }
    assert extract_area(item) == (118.0, None)


def test_area_mtk_fallback_without_props() -> None:
    item = {"unit": {"code": "MTK"}, "quantity": 141.3, "itemProps": None}
    assert extract_area(item) == (141.3, None)


def test_area_zero_is_kept() -> None:
    item = {"unit": {"code": "LO"}, "itemProps": {"totalObjectArea": 0.0}}
    assert extract_area(item) == (0.0, None)


def test_area_har_is_land() -> None:
    item = {"unit": {"code": "HAR"}, "quantity": 2.5}
    assert extract_area(item) == (None, 2.5)


def test_area_unknown_unit() -> None:
    item = {"unit": {"code": "LO"}}
    assert extract_area(item) == (None, None)


def test_area_empty_item() -> None:
    assert extract_area({}) == (None, None)


def test_area_mtk_uses_quantity_on_real_data(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    assert extract_area(raw["items"][0]) == (141.3, None)


def test_area_mtk_with_props_on_real_data(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261008-61071")
    assert extract_area(raw["items"][0]) == (1893.2, None)


def test_area_any_with_props_on_real_data(load_fixture: LoadFixture) -> None:
    raw = load_fixture("BRE001-UA-20261013-85203")
    assert extract_area(raw["items"][0]) == (118.0, None)


def test_no_area_on_real_data(load_fixture: LoadFixture) -> None:
    raw = load_fixture("BRE001-UA-20260525-60638")
    assert extract_area(raw["items"][0]) == (None, None)


def test_normalize_real_estate_lot(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))

    assert isinstance(lot, Lot)
    assert lot.auction_id == "CSE001-UA-20261003-41261"
    assert lot.status == "unsuccessful"
    assert lot.selling_method == "commercialSell-english"
    assert lot.tender_attempts == 1
    assert lot.previous_auction_id is None
    assert lot.start_price == 219857.0
    assert lot.currency == "UAH"
    assert lot.cav_code == "04000000-8"
    assert lot.region == "Чернігівська область"
    assert lot.locality == "Кучинівка"
    assert lot.area_m2 == 141.3
    assert lot.land_area_ha is None
    assert lot.auction_date == "2026-11-02T10:55:00.000000Z"
    assert lot.source_url == "https://prozorro.sale/auction/CSE001-UA-20261003-41261/"


def test_normalize_first_attempt_has_no_previous(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("BRE001-UA-20260525-60638"))
    assert lot.previous_auction_id is None
    assert lot.tender_attempts == 1
    assert lot.area_m2 is None


def test_normalize_without_address(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("BRE001-UA-20261013-44974"))
    assert lot.region is None
    assert lot.locality is None
    assert lot.tender_attempts == 3


def test_normalize_requires_id_and_auction_id() -> None:
    with pytest.raises(KeyError):
        normalize({})


def test_normalize_requires_auction_id() -> None:
    with pytest.raises(KeyError):
        normalize({"_id": "x"})
