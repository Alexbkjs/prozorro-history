"""Turn raw Prozorro.Sale records into flat, typed Lot objects."""

from dataclasses import dataclass
from typing import Any

from prozorro_history.client import BASE_URL


@dataclass(frozen=True, slots=True)
class Lot:
    """One auction record, flattened to the fields we care about.

    Immutable (frozen). Only procedure_id, auction_id, source_url and api_url
    are always present. Every other field is None when the raw record lacks it.
    """

    procedure_id: str  # _id
    auction_id: str
    previous_auction_id: str | None
    tender_attempts: int | None
    status: str | None
    selling_method: str | None
    date_modified: str | None
    title: str | None
    start_price: float | None  # value.amount
    currency: str | None
    cav_code: str | None  # items[0].classification.id
    region: str | None
    locality: str | None
    area_m2: float | None
    land_area_ha: float | None
    auction_date: str | None  # auctionPeriod.startDate
    source_url: str  # https://prozorro.sale/auction/{auction_id}/
    api_url: str


def ua(value: dict[str, str] | None) -> str | None:
    """Pick a plain string out of a language dict.

    Accepts a dict like {"uk_UA": "Київ", "en_US": "Kyiv"} and returns the
    Ukrainian text, falling back to English. Returns None if the value is
    None or holds neither language.
    """
    if value is None:
        return None
    return value.get("uk_UA") or value.get("en_US")


def extract_area(item: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract (area_m2, land_area_ha) from one auction item.

    Rules, in priority order:
    1. itemProps.totalObjectArea, if present, is area_m2. It is the structured
       field, so it wins over the unit: quantity can disagree with it
       (e.g. unit MTK, quantity 1.0, totalObjectArea 1893.2).
    2. Otherwise, unit MTK (square metres): quantity is area_m2.
    3. Unit HAR (hectares): quantity is land_area_ha.
    4. Anything else: (None, None).

    Known limitations:
    - Only one item is looked at. The caller passes items[0], so lots with
      several items lose the rest.
    - When totalObjectArea is present the function returns early, so
      land_area_ha is None even for a HAR item. The sampled data never has
      both together.
    - The MTK fallback can be wrong: a record with unit MTK and quantity 1.0
      but no itemProps would give 1 m². The data cannot tell us.
    """
    item_props = item.get("itemProps") or {}
    area_m2 = item_props.get("totalObjectArea")
    if area_m2 is not None:
        return (area_m2, None)

    unit = item.get("unit") or {}
    code = unit.get("code")

    area_m2 = item.get("quantity") if code == "MTK" else None
    land_ha = item.get("quantity") if code == "HAR" else None

    return area_m2, land_ha


def normalize(raw: dict[str, Any]) -> Lot:
    """Convert one raw API record into a Lot.

    "_id" and "auctionId" identify the record, so they are read directly and a
    missing one raises KeyError: a record without them is broken. Every other
    field is optional and becomes None when absent.

    Known limitation: only the first item (items[0]) is read, so area, CAV
    code and address come from that item alone.
    """
    procedure_id = raw["_id"]
    auction_id = raw["auctionId"]
    items = raw.get("items") or []
    item = items[0] if items else {}
    previous_auction_id = raw.get("previousAuctionId")
    tender_attempts = raw.get("tenderAttempts")
    status = raw.get("status")
    selling_method = raw.get("sellingMethod")
    date_modified = raw.get("dateModified")
    title = ua(raw.get("title"))
    start_price = (raw.get("value") or {}).get("amount")
    currency = (raw.get("value") or {}).get("currency")
    cav_code = (item.get("classification") or {}).get("id")
    address = item.get("address") or {}
    region = ua(address.get("region"))
    locality = ua(address.get("locality"))
    area_m2, land_area_ha = extract_area(item)
    auction_date = (raw.get("auctionPeriod") or {}).get("startDate")
    source_url = f"https://prozorro.sale/auction/{auction_id}/"
    api_url = f"{BASE_URL}search/byAuctionId/{auction_id}"

    return Lot(
        procedure_id=procedure_id,
        auction_id=auction_id,
        previous_auction_id=previous_auction_id,
        tender_attempts=tender_attempts,
        status=status,
        selling_method=selling_method,
        date_modified=date_modified,
        title=title,
        start_price=start_price,
        currency=currency,
        cav_code=cav_code,
        region=region,
        locality=locality,
        area_m2=area_m2,
        land_area_ha=land_area_ha,
        auction_date=auction_date,
        source_url=source_url,
        api_url=api_url,
    )
