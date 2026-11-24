from collections.abc import Callable
from dataclasses import replace
from typing import Any

from prozorro_history.normalize import normalize
from prozorro_history.verify import classify, compare

LoadFixture = Callable[[str], dict[str, Any]]


def test_identical_lots_have_no_mismatches(load_fixture: LoadFixture) -> None:
    lot = normalize(load_fixture("CSE001-UA-20261003-41261"))
    assert compare(lot, lot) == []
    assert classify(lot, lot) == ("ok", [])


def test_changed_status_is_reported(load_fixture: LoadFixture) -> None:
    stored = normalize(load_fixture("CSE001-UA-20261003-41261"))
    live = replace(stored, status="complete")

    problems = compare(stored, live)

    assert len(problems) == 1
    assert problems[0].field == "status"
    assert problems[0].stored == "unsuccessful"
    assert problems[0].live == "complete"


def test_difference_with_same_date_is_a_mismatch(load_fixture: LoadFixture) -> None:
    stored = normalize(load_fixture("CSE001-UA-20261003-41261"))
    live = replace(stored, start_price=1.0)
    verdict, problems = classify(stored, live)
    assert verdict == "mismatch"
    assert [p.field for p in problems] == ["start_price"]


def test_difference_with_newer_live_date_is_outdated(
    load_fixture: LoadFixture,
) -> None:
    stored = normalize(load_fixture("CSE001-UA-20261003-41261"))
    live = replace(
        stored, status="complete", date_modified="2099-01-01T00:00:00.000000Z"
    )
    verdict, _ = classify(stored, live)
    assert verdict == "outdated"
