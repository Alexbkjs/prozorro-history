"""Follow previousAuctionId links to rebuild an auction's history."""

from collections.abc import Callable

from prozorro_history.normalize import Lot

Lookup = Callable[[str], Lot | None]  # auction_id -> Lot, or None if unknown


def resolve_chain(lot: Lot, lookup: Lookup, max_depth: int = 20) -> list[Lot]:
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
