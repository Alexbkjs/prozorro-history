"""HTTP client for the Prozorro.Sale API."""

import time
from collections.abc import Iterator
from typing import Any, Self

import httpx

BASE_URL = "https://procedure.prozorro.sale/api/"


class ProzorroClient:
    """Thin wrapper around httpx with retries and a paginated feed reader.

    Use it as a context manager so the connection is closed automatically:

        with ProzorroClient() as client:
            auction = client.get_by_auction_id("LLE001-UA-20261005-41838")
    """

    def __init__(self, timeout: float = 30, max_retries: int = 4, page_size: int = 100):
        self.max_retries = max_retries
        self.page_size = page_size
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"User-Agent": "prozorro-history/0.1"},
        )

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET a path, retrying temporary failures with exponential backoff.

        Retries on HTTP 429, HTTP 5xx and network errors, waiting 1s, 2s,
        4s... between attempts. Any other response (including 404) is
        returned as-is so the caller can decide what it means. Raises
        RuntimeError once all attempts are used up.
        """
        last_problem: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as e:
                last_problem = repr(e)
            else:
                if response.status_code != 429 and response.status_code < 500:
                    return response
                last_problem = f"HTTP {response.status_code}"

            if attempt < self.max_retries:
                time.sleep(2**attempt)

        raise RuntimeError(
            f"Request to '{path}' failed after {self.max_retries + 1} "
            f"attempts. Last problem: {last_problem}"
        )

    def get_by_auction_id(self, auction_id: str) -> dict[str, Any] | None:
        """Return the auction as a dict, or None if it does not exist."""
        response = self._get(f"search/byAuctionId/{auction_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    def iter_feed(self, since: str) -> Iterator[dict[str, Any]]:
        """Yield feed records modified at or after `since`, oldest first.

        This is a generator: it fetches one page at a time and yields its
        records, so years of data are never held in memory and the caller
        can stop whenever it wants.

        Records are unique by _id. The API returns the record at the cursor
        again at the start of the next page, so ids seen at the current
        cursor timestamp are remembered and skipped.

        Raises RuntimeError if a full page shares one dateModified equal to
        the cursor, because the cursor could never move past it.
        """
        cursor = since
        seen_at_cursor: set[str] = set()
        while True:
            response = self._get(
                f"search/byDateModified/{cursor}",
                params={"limit": self.page_size},
            )
            response.raise_for_status()
            page = response.json()
            if not page:
                return
            if (
                len(page) == self.page_size
                and page[0]["dateModified"] == page[-1]["dateModified"] == cursor
            ):
                raise RuntimeError(
                    f"Feed cursor is stuck at {cursor}: a full page of "
                    f"{self.page_size} records all share this dateModified, "
                    "so the next page cannot be reached."
                )
            new_records = [r for r in page if r["_id"] not in seen_at_cursor]
            if not new_records:
                return
            yield from new_records
            cursor = page[-1]["dateModified"]
            seen_at_cursor = {r["_id"] for r in page if r["dateModified"] == cursor}
