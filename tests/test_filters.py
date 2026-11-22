from collections.abc import Callable
from dataclasses import replace
from typing import Any

from prozorro_history.filters import is_real_estate
from prozorro_history.normalize import normalize

LoadFixture = Callable[[str], dict[str, Any]]


def test_real_estate_fixture_is_kept(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    assert is_real_estate(lot) is True


def test_machinery_fixture_is_rejected(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("BRE001-UA-20260525-60638"))
    assert is_real_estate(lot) is False


def test_sub_code_under_04_is_kept(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    lot2 = replace(lot, cav_code="04232000-3")
    assert is_real_estate(lot2) is True


def test_land_is_rejected(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    lot2 = replace(lot, cav_code="06121000-6")
    assert is_real_estate(lot2) is False


def test_missing_code_is_rejected(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    lot2 = replace(lot, cav_code=None)
    assert is_real_estate(lot2) is False


def test_prefix_not_substring(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    lot2 = replace(lot, cav_code="34040000-1")
    assert is_real_estate(lot2) is False
