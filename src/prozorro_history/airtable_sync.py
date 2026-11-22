"""Send lots to Airtable for human review."""

from typing import Any

from prozorro_history.history import ChainInfo
from prozorro_history.normalize import Lot

# Fields people edit in Airtable. The sync must never send these, so a
# re-run can't wipe someone's review.
REVIEW_FIELDS = {"Reviewed", "Notes"}


def to_airtable_fields(lot: Lot, info: ChainInfo) -> dict[str, Any]:
    """Build the Airtable fields for one lot. Keys must match the column names exactly."""
    return {
        "auction_id": lot.auction_id,
        "chain_id": info.chain_id,
        "attempt_no": info.attempt_no,
        "status": lot.status,
        "selling_method": lot.selling_method,
        "title": lot.title,
        "region": lot.region,
        "locality": lot.locality,
        "area_m2": lot.area_m2,
        "start_price": lot.start_price,
        "failed_attempts": info.failed_attempts,
        "price_change_vs_first_pct": info.price_change_vs_first_pct,
        "chain_complete": info.chain_complete,
        "source_url": lot.source_url,
        "api_url": lot.api_url,
        "auction_date": lot.auction_date[:10] if lot.auction_date is not None else None,
    }
