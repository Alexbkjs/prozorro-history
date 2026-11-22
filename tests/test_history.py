from collections.abc import Callable
from dataclasses import replace
from typing import Any

from prozorro_history.history import resolve_chain, summarize_chain
from prozorro_history.normalize import Lot, normalize

LoadFixture = Callable[[str], dict[str, Any]]

CHAIN_IDS = [
    "BRE001-UA-20260525-60638",  # attempt 1, unsuccessful
    "BRE001-UA-20260820-86926",  # attempt 2, unsuccessful
    "BRD001-UA-20261010-26702",  # attempt 3, complete
]


def test_full_chain_oldest_first(load_fixture: LoadFixture) -> None:
    lots = {aid: normalize(load_fixture(aid)) for aid in CHAIN_IDS}
    chain = resolve_chain(lots["BRD001-UA-20261010-26702"], lots.get)
    assert [lot.auction_id for lot in chain] == CHAIN_IDS


def test_missing_link_stops(load_fixture: LoadFixture) -> None:
    # 44974 points to BRE001-UA-20260909-79216, which we never saved
    lot = normalize(load_fixture("BRE001-UA-20261013-44974"))
    empty: dict[str, Lot] = {}
    chain = resolve_chain(lot, empty.get)
    assert [x.auction_id for x in chain] == ["BRE001-UA-20261013-44974"]


def test_circular_loop_with_lots_pointing_at_each_other(
    load_fixture: LoadFixture,
) -> None:
    lot = normalize(load_fixture("BRE001-UA-20261013-44974"))
    fake_lot_a = replace(lot, auction_id="a", previous_auction_id="b")
    fake_lot_b = replace(lot, auction_id="b", previous_auction_id="a")
    lots = {"a": fake_lot_a, "b": fake_lot_b}
    chain = resolve_chain(fake_lot_a, lots.get)
    assert [lot.auction_id for lot in chain] == [
        fake_lot_b.auction_id,
        fake_lot_a.auction_id,
    ]


def test_full_chain(load_fixture: LoadFixture) -> None:
    lots = {aid: normalize(load_fixture(aid)) for aid in CHAIN_IDS}
    chain = resolve_chain(lots["BRD001-UA-20261010-26702"], lots.get)
    info = summarize_chain(chain)
    assert info.chain_id == "BRE001-UA-20260525-60638"
    assert info.attempt_no == 3
    assert info.failed_attempts == 2
    assert info.price_change_vs_first_pct == -40.0
    assert info.chain_complete is True


def test_single_first_attempt(load_fixture: LoadFixture) -> None:
    chain = [normalize(load_fixture("CSE001-UA-20261003-41261"))]
    info = summarize_chain(chain)
    assert info.chain_id == "CSE001-UA-20261003-41261"
    assert info.attempt_no == 1
    assert info.failed_attempts == 1
    assert info.price_change_vs_first_pct == 0.0
    assert info.chain_complete is True


def test_missing_link(load_fixture: LoadFixture) -> None:
    chain = [normalize(load_fixture("BRE001-UA-20261013-44974"))]
    info = summarize_chain(chain)
    assert info.attempt_no == 3
    assert info.failed_attempts == 1
    assert info.price_change_vs_first_pct == 0.0
    assert info.chain_complete is False


def test_missing_price(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("BRE001-UA-20261013-44974"))
    lot_with_no_price = replace(lot, start_price=None)
    chain = [lot_with_no_price]
    info = summarize_chain(chain)
    assert info.price_change_vs_first_pct is None


def test_price_change_keeps_one_decimal(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    chain = [replace(lot, start_price=100.0), replace(lot, start_price=87.66)]
    info = summarize_chain(chain)
    assert info.price_change_vs_first_pct == -12.3
