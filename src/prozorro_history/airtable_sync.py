"""Send lots to Airtable for human review."""

from typing import Any

from pyairtable import Table

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


def push_rows(table: Table, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Create or update rows in Airtable, matched on auction_id.

    Returns (created, updated) counts. Running it twice with the same rows
    gives (0, n) the second time: no duplicates.
    """
    if not rows:
        return (0, 0)
    records = [{"fields": row} for row in rows]
    result = table.batch_upsert(
        records,
        key_fields=["auction_id"],
        replace=False,
    )
    created = len(result["createdRecords"])
    updated = len(result["updatedRecords"])
    return (created, updated)
