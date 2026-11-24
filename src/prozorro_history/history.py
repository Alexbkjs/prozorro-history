"""Follow previousAuctionId links to rebuild an auction's history."""

from collections.abc import Callable
from dataclasses import dataclass

from prozorro_history.normalize import Lot


@dataclass(frozen=True, slots=True)
class ChainInfo:
    chain_id: str  # auction_id of the oldest attempt we found
    attempt_no: int  # number of attempts found by following the links (1, 2, 3...)
    failed_attempts: int  # how many attempts in the chain ended "unsuccessful"
    price_change_vs_first_pct: float | None  # e.g. -40.0; None if a price is missing
    chain_complete: bool  # True if the oldest lot really is attempt 1


Lookup = Callable[[str], Lot | None]  # auction_id -> Lot, or None if unknown


def resolve_chain(lot: Lot, lookup: Lookup, max_depth: int = 100) -> list[Lot]:
    """Return every attempt we can find for this object, oldest first.

    Stops when:
    - there is no previous_auction_id (we reached the first attempt),
    - lookup returns None (a missing link: the chain is incomplete),
    - an auction_id repeats (a loop in the data; should never happen),
    - max_depth attempts were collected (a safety limit).
    """
    chain = [lot]
    seen = {lot.auction_id}
    current = lot
    while current.previous_auction_id and len(chain) < max_depth:
        prev_id = current.previous_auction_id
        if prev_id in seen:
            break
        prev = lookup(prev_id)
        if prev is None:
            break
        chain.append(prev)
        seen.add(prev_id)
        current = prev

    chain.reverse()
    return chain


def summarize_chain(chain: list[Lot]) -> ChainInfo:
    """Summarize a chain from resolve_chain (oldest first).

    attempt_no counts the attempts we actually followed, not the platform's
    tenderAttempts field: in real data tenderAttempts stops growing at 10
    while repeat auctions continue for years (e.g. a 39-attempt lease chain).

    Known limitation: if a link is missing, chain_id is the oldest attempt we
    *could* find. When the missing attempt is fetched later, chain_id changes.
    """
    first = chain[0]
    last = chain[-1]
    attempt_no = len(chain)
    failed_attempts = sum(1 for x in chain if x.status == "unsuccessful")
    pct = _pct_change(first.start_price, last.start_price)
    complete = first.previous_auction_id is None and (first.tender_attempts or 1) == 1
    return ChainInfo(
        chain_id=first.auction_id,
        attempt_no=attempt_no,
        failed_attempts=failed_attempts,
        price_change_vs_first_pct=pct,
        chain_complete=complete,
    )


def _pct_change(old: float | None, new: float | None) -> float | None:
    """Percent change from old to new, rounded to 1 decimal place.

    Returns None if either price is missing or old is 0 (we can't divide by 0).
    """
    if old is None or new is None or old == 0:
        return None
    return round((new - old) / old * 100, 1)
