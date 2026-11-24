import argparse
import logging
import sqlite3
from typing import Any

from prozorro_history import storage
from prozorro_history.airtable_sync import open_table, push_rows, to_airtable_fields
from prozorro_history.client import ProzorroClient
from prozorro_history.filters import is_real_estate
from prozorro_history.history import Lookup, resolve_chain, summarize_chain
from prozorro_history.normalize import Lot, normalize

DEFAULT_DB = "data/prozorro.db"
log = logging.getLogger("prozorro_history")


def cmd_fetch(args: argparse.Namespace) -> None:
    """Download new and changed auctions from the feed into SQLite."""
    conn = storage.connect(args.db)
    since = args.since or storage.get_cursor(conn)
    if since is None:
        raise SystemExit(
            "No saved cursor yet. Pass --since, e.g. --since 2026-11-01T00:00:00"
        )

    seen = changed = 0
    with ProzorroClient() as client:
        for raw in client.iter_feed(since):
            lot = normalize(raw)
            with conn:  # one transaction: the record and the cursor are saved together
                if storage.upsert_lot(conn, lot, raw):
                    changed += 1
                storage.set_cursor(conn, raw["dateModified"])
            seen += 1
            if args.limit is not None and seen >= args.limit:
                break
    log.info("fetch done: %d records read, %d new or changed", seen, changed)


def make_lookup(conn: sqlite3.Connection, client: ProzorroClient) -> Lookup:
    """Find an attempt by auction_id: SQLite first, then the API (and save it)."""

    def lookup(auction_id: str) -> Lot | None:
        lot = storage.get_lot(conn, auction_id)
        if lot is not None:
            return lot
        raw = client.get_by_auction_id(auction_id)
        if raw is None:
            return None
        lot = normalize(raw)
        with conn:
            storage.upsert_lot(conn, lot, raw)
        return lot

    return lookup


def cmd_sync(args: argparse.Namespace) -> None:
    """Push one row per real-estate object (its newest attempt) to Airtable.

    The full history stays in SQLite; Airtable gets the summary of it
    (attempts found, failed attempts, price change, completeness).
    """
    conn = storage.connect(args.db)
    table = open_table()
    lots = [lot for lot in storage.latest_attempts(conn) if is_real_estate(lot)]
    log.info("sync: %d real-estate lots in scope, building chains...", len(lots))

    rows: list[dict[str, Any]] = []
    with ProzorroClient() as client:
        lookup = make_lookup(conn, client)
        for lot in lots:
            chain = resolve_chain(lot, lookup)
            rows.append(to_airtable_fields(lot, summarize_chain(chain)))

    created, updated = push_rows(table, rows)
    log.info("sync done: %d created, %d updated", created, updated)


def main() -> None:
    parser = argparse.ArgumentParser(prog="prozorro-history")
    parser.add_argument(
        "--db", default=DEFAULT_DB, help="SQLite file (default: %(default)s)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser(
        "fetch", help="Download new and changed auctions into SQLite"
    )
    p_fetch.add_argument(
        "--since", help="Start time; default: continue from the saved cursor"
    )
    p_fetch.add_argument("--limit", type=int, help="Stop after this many records")
    p_fetch.set_defaults(func=cmd_fetch)

    p_sync = sub.add_parser(
        "sync", help="Push real-estate lots and their history to Airtable"
    )
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args.func(args)
