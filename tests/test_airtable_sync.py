from collections.abc import Callable
from typing import Any

from prozorro_history.airtable_sync import REVIEW_FIELDS, to_airtable_fields
from prozorro_history.history import resolve_chain, summarize_chain
from prozorro_history.normalize import normalize

LoadFixture = Callable[[str], dict[str, Any]]

CHAIN_IDS = [
    "BRE001-UA-20260525-60638",  # attempt 1, unsuccessful
    "BRE001-UA-20260820-86926",  # attempt 2, unsuccessful
    "BRD001-UA-20261010-26702",  # attempt 3, complete
]


def test_full_chain(load_fixture: LoadFixture) -> None:
    lots = {aid: normalize(load_fixture(aid)) for aid in CHAIN_IDS}
    chain = resolve_chain(lots["BRD001-UA-20261010-26702"], lots.get)
    info = summarize_chain(chain)
    fields = to_airtable_fields(chain[-1], info)
    assert fields["auction_id"] == "BRD001-UA-20261010-26702"
    assert fields["chain_id"] == "BRE001-UA-20260525-60638"
    assert fields["price_change_vs_first_pct"] == -40.0
    assert len(fields["auction_date"]) == 10
    assert fields["source_url"].startswith("https://prozorro.sale/auction/")


def test_review_fields_never_sent(load_fixture: LoadFixture) -> None:
    lots = {aid: normalize(load_fixture(aid)) for aid in CHAIN_IDS}
    chain = resolve_chain(lots["BRD001-UA-20261010-26702"], lots.get)
    info = summarize_chain(chain)
    fields = to_airtable_fields(chain[-1], info)
    assert REVIEW_FIELDS.isdisjoint(fields)
