from collections.abc import Callable
from dataclasses import replace
from typing import Any

from prozorro_history.normalize import normalize
from prozorro_history.storage import (
    all_lots,
    connect,
    get_cursor,
    get_lot,
    set_cursor,
    upsert_lot,
)

LoadFixture = Callable[[str], dict[str, Any]]


def test_insert_new_lot(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    lot = normalize(raw)
    conn = connect(":memory:")

    assert upsert_lot(conn, lot, raw) is True
    assert get_lot(conn, lot.auction_id) == lot


def test_same_lot_twice_is_not_a_change(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    lot = normalize(raw)
    conn = connect(":memory:")

    upsert_lot(conn, lot, raw)
    assert upsert_lot(conn, lot, raw) is False
    count = conn.execute("SELECT COUNT(*) FROM lots").fetchone()[0]
    assert count == 1


def test_newer_date_updates_status(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    lot = normalize(raw)
    base = replace(
        lot,
        status="active",
        date_modified="2026-01-01T00:00:00.000000Z",
    )
    newer = replace(
        base,
        status="complete",
        date_modified="2026-02-01T00:00:00.000000Z",
    )
    conn = connect(":memory:")

    upsert_lot(conn, base, raw)
    assert upsert_lot(conn, newer, raw) is True
    stored = get_lot(conn, lot.auction_id)
    assert stored is not None
    assert stored.status == "complete"


def test_older_date_does_not_downgrade(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    lot = normalize(raw)
    base = replace(
        lot,
        status="complete",
        date_modified="2026-02-01T00:00:00.000000Z",
    )
    older = replace(
        base,
        status="active",
        date_modified="2026-01-01T00:00:00.000000Z",
    )

    conn = connect(":memory:")

    upsert_lot(conn, base, raw)
    assert upsert_lot(conn, older, raw) is False

    stored = get_lot(conn, lot.auction_id)
    assert stored is not None
    assert stored.status == "complete"


def test_cursor_starts_empty_and_round_trips() -> None:
    conn = connect(":memory:")

    assert get_cursor(conn) is None
    set_cursor(conn, "2026-11-20T10:00:00.000000Z")
    assert get_cursor(conn) == "2026-11-20T10:00:00.000000Z"


def test_all_lots_returns_every_lot(load_fixture: LoadFixture) -> None:
    raw = load_fixture("CSE001-UA-20261003-41261")
    lot_a = normalize(raw)
    lot_b = replace(lot_a, procedure_id="123", auction_id="456")
    conn = connect(":memory:")

    upsert_lot(conn, lot_a, raw)
    upsert_lot(conn, lot_b, raw)

    lots = all_lots(conn)
    assert len(lots) == 2
    assert {lot.auction_id for lot in lots} == {lot_a.auction_id, lot_b.auction_id}
