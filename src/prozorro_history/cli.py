"""Command-line entry point: uv run prozorro-history <command>.

Commands: fetch (feed -> SQLite), sync (SQLite -> Airtable),
verify (re-check a sample against Prozorro.Sale).
"""

import argparse
import logging
import random
import sqlite3
from typing import Any

import httpx

from prozorro_history import storage
from prozorro_history.airtable_sync import open_table, push_rows, to_airtable_fields
from prozorro_history.client import ProzorroClient
from prozorro_history.filters import is_real_estate
from prozorro_history.history import Lookup, resolve_chain, summarize_chain
from prozorro_history.normalize import Lot, normalize
from prozorro_history.verify import classify

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
            log.info("%s: earlier attempt not found in the API", auction_id)
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


def cmd_verify(args: argparse.Namespace) -> None:
    """Re-fetch a random sample of lots and compare them with SQLite.

    Exits with code 1 on a real mismatch or a broken source link, so a cron
    job or CI can alert on it. "Outdated" lots are not failures.
    """
    conn = storage.connect(args.db)
    lots = [lot for lot in storage.latest_attempts(conn) if is_real_estate(lot)]
    sample = random.Random(args.seed).sample(lots, min(args.sample, len(lots)))

    counts = {"ok": 0, "outdated": 0, "mismatch": 0, "missing": 0, "bad_link": 0}
    with ProzorroClient() as client, httpx.Client(timeout=30) as web:
        for stored in sample:
            raw = client.get_by_auction_id(stored.auction_id)
            if raw is None:
                counts["missing"] += 1
                log.warning("%s: no longer in the API", stored.auction_id)
                continue

            if web.get(stored.source_url).status_code != 200:
                counts["bad_link"] += 1
                log.warning("%s: source_url does not open", stored.auction_id)

            verdict, problems = classify(stored, normalize(raw))
            counts[verdict] += 1
            for p in problems:
                level = logging.WARNING if verdict == "mismatch" else logging.INFO
                log.log(
                    level,
                    "%s [%s] %s: stored=%r live=%r",
                    p.auction_id,
                    verdict,
                    p.field,
                    p.stored,
                    p.live,
                )

    log.info(
        "verify: %d checked, %d ok, %d outdated (run fetch), %d MISMATCHED, "
        "%d missing, %d bad links",
        len(sample),
        counts["ok"],
        counts["outdated"],
        counts["mismatch"],
        counts["missing"],
        counts["bad_link"],
    )
    if counts["mismatch"] or counts["bad_link"]:
        raise SystemExit(1)


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
        "sync", help="Push one row per real-estate object to Airtable"
    )
    p_sync.set_defaults(func=cmd_sync)

    p_verify = sub.add_parser(
        "verify", help="Re-check a random sample against Prozorro.Sale"
    )
    p_verify.add_argument(
        "--sample", type=int, default=20, help="How many lots (default: %(default)s)"
    )
    p_verify.add_argument(
        "--seed", type=int, help="Random seed, to repeat the same sample"
    )
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    # httpx logs every request at INFO; we log the events that matter ourselves.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args.func(args)
