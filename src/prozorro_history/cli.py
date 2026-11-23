import argparse
import logging

from prozorro_history import storage
from prozorro_history.client import ProzorroClient
from prozorro_history.normalize import normalize

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

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args.func(args)
