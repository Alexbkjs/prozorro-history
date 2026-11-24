"""Re-check stored lots against the primary source (Prozorro.Sale)."""

from dataclasses import dataclass
from typing import Literal

from prozorro_history.normalize import Lot

# The fields a reviewer relies on. If one of these is wrong, the Airtable row is wrong.
CHECKED_FIELDS = (
    "status",
    "start_price",
    "previous_auction_id",
    "auction_date",
    "area_m2",
)

Verdict = Literal["ok", "outdated", "mismatch"]


@dataclass(frozen=True, slots=True)
class Mismatch:
    auction_id: str
    field: str
    stored: object
    live: object


def compare(stored: Lot, live: Lot) -> list[Mismatch]:
    """Return one Mismatch per checked field that differs. Empty list = all good."""
    problems = []
    for name in CHECKED_FIELDS:
        stored_value = getattr(stored, name)
        live_value = getattr(live, name)
        if stored_value != live_value:
            problems.append(Mismatch(stored.auction_id, name, stored_value, live_value))
    return problems


def classify(stored: Lot, live: Lot) -> tuple[Verdict, list[Mismatch]]:
    """Decide whether a difference is a real error or just a newer version.

    - "ok": every checked field matches.
    - "outdated": fields differ, but the live record was modified after ours.
      Normal: the auction moved on. Running `fetch` fixes it.
    - "mismatch": fields differ although both copies have the same
      date_modified. Our normalizing or storage got something wrong.
    """
    problems = compare(stored, live)
    if not problems:
        return "ok", problems
    if (live.date_modified or "") > (stored.date_modified or ""):
        return "outdated", problems
    return "mismatch", problems
