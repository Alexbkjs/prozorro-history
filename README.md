# prozorro-history

Collects the **history of real-estate lots on [Prozorro.Sale](https://prozorro.sale)**: failed auctions, repeat auctions and price changes between attempts. It keeps a link to the primary source for every lot, never stores duplicates, and pushes one summary row per object to **Airtable** for human review.

```
Prozorro.Sale API ──fetch──▶ SQLite (source of truth, raw JSON kept)
                                │
                                ├─sync──▶ Airtable (one row per object, review fields untouched)
                                │
                                └─verify─▶ re-fetch a sample from the source and compare
```

## What it found (feed of 1–2 Nov 2026)

- **211 real-estate objects**: 142 have at least one failed auction, and **81 have failed 5 or more times**.
- **Chains are long.** The longest has **40 attempts**: a commercial lease in Kharkiv, re-auctioned roughly monthly since August 2022 (`CLE001-UA-20261102-57343`).
- **67 objects** are now offered at least 30% below their first starting price.
- **The platform's own `tenderAttempts` counter can't be trusted for long chains.** It stays at `10` for years while repeat auctions continue. The attempt number here comes from following `previousAuctionId` links instead.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync
cp .env.example .env          # fill in your Airtable token, base ID and table ID

uv run prozorro-history fetch --since 2026-11-01T00:00:00 --limit 500
uv run prozorro-history sync
uv run prozorro-history verify --sample 20
```

| Command | What it does |
|---|---|
| `fetch [--since TS] [--limit N]` | Reads the change feed into SQLite. Without `--since`, it continues from the saved cursor. |
| `sync` | Builds each real-estate object's chain of attempts and upserts one row per object to Airtable. |
| `verify [--sample N] [--seed S]` | Re-fetches N random lots from the API and checks they match SQLite and that the public page opens. Exits with 1 on a real mismatch. |

All commands accept `--db PATH` (default `data/prozorro.db`).

### Airtable table

Create a table with these fields. The names are case-sensitive.

| Field | Type | Owner |
|---|---|---|
| `auction_id` (primary) | Single line text | sync |
| `chain_id`, `status`, `selling_method`, `region`, `locality` | Single line text | sync |
| `title` | Long text | sync |
| `attempt_no`, `failed_attempts`, `area_m2`, `start_price`, `price_change_vs_first_pct` | Number (decimals for area, price and pct) | sync |
| `chain_complete` | Checkbox | sync |
| `auction_date` | Date | sync |
| `source_url`, `api_url` | URL | sync |
| `Reviewed` | Checkbox | **people** |
| `Notes` | Long text | **people** |

The token needs the `data.records:read` and `data.records:write` scopes on this base. Set `AIRTABLE_TABLE` to the table ID (`tbl…`) rather than its name, so renaming the table doesn't break the sync.

## Design decisions

**SQLite is the source of truth, and Airtable is the review layer.** Everything from the feed is stored, including land, vehicles and so on, together with the raw JSON. Scope is applied only when syncing (`filters.is_real_estate`). Widening the scope, for example to land, means changing one function, with no re-download. Airtable's record limits and rate limits never constrain collection.

**Duplicates are prevented at three levels:**
1. **Feed.** The feed boundary is inclusive, so the last record of a page comes back first on the next page. `client.iter_feed` skips `_id`s already seen at the cursor timestamp, and it raises an error if a full page shares one timestamp, because the cursor could never move past it.
2. **Storage.** The primary key is `procedure_id`, and a row is overwritten only when the incoming `dateModified` is newer. Re-reading the feed is therefore harmless.
3. **Airtable.** `batch_upsert` matches on `auction_id`, so a second `sync` reports `0 created`.

**A repeat auction is not a duplicate.** It's another attempt at the same object. `history.resolve_chain` follows `previousAuctionId` back to the first attempt, with a loop guard and a depth limit. Earlier attempts missing from SQLite are fetched from the API once and cached. Airtable gets one row per object (`storage.latest_attempts`: the attempt nothing points back to) with the history summarized: `attempt_no`, `failed_attempts`, `price_change_vs_first_pct` and `chain_complete`.

**Review fields are never overwritten.** `Reviewed` and `Notes` are never sent (a test enforces this), and the upsert uses `replace=False`, so Airtable leaves fields we don't send unchanged.

**Crash-safe resume.** Each record and the cursor are committed in one SQLite transaction, so an interrupted `fetch` never skips data.

**Polite HTTP client.** It has timeouts, and it retries with exponential backoff on 429, 5xx and network errors. A 404 is treated as a normal answer ("not found"), not a crash.

## Verifying the data

- **Every row has `source_url`**, the public auction page (`https://prozorro.sale/auction/{auctionId}/`), and `api_url`, the exact API record.
- **`verify` re-fetches a random sample and compares** status, start price, previous auction, auction date and area. A difference is classified as:
  - **outdated**: the live record was modified after ours. That's normal, and `fetch` fixes it.
  - **mismatch**: same `dateModified`, different values, which means a bug in our code. It exits with 1.
- **Example run** over all 211 objects: `209 ok, 2 outdated, 0 MISMATCHED, 0 missing, 0 bad links`.

## Data notes and known limitations

- **Area** comes from `items[].itemProps.totalObjectArea` when present. Otherwise it falls back to `quantity` when the unit is `MTK` (m²). Hectares (`HAR`) go to a separate land field. Using `quantity` blindly gives wrong results: for example, a record with unit `MTK` and `quantity` 1.0 actually has `totalObjectArea` 1893.2.
- **Only the first item** of a lot is used for area, CAV code and address.
- **Real estate means CAV `04…`.** Land (`06…`) is out of scope for now.
- **Incomplete chains.** Some chains reach records from the previous system (`UA-PS-…`) that don't link further back. A few others point to auctions the API doesn't return (404). These are flagged `chain_complete = false`, and their `chain_id` is the oldest attempt found.
- **Missing earlier attempts are re-requested on every `sync`**, because "not found" isn't cached yet.

## Running on a server (Linux)

```cron
# every hour: pull changes, push to Airtable; every night: verify a sample
0 * * * *  cd /opt/prozorro-history && { uv run prozorro-history fetch && uv run prozorro-history sync; } >> logs/sync.log 2>&1
30 3 * * * cd /opt/prozorro-history && uv run prozorro-history verify --sample 50 >> logs/verify.log 2>&1
```

Cron runs with a minimal `PATH`, so use the full path to `uv` (`which uv`) or set `PATH=` at the top of the crontab. Use `uv sync --frozen` on the server, so it installs exactly the versions in `uv.lock`.

## Development

```bash
uv run pytest        # 51 tests; offline, using real API records in tests/fixtures/
uv run mypy          # strict
uv run ruff check && uv run ruff format --check
```

| Module | Responsibility |
|---|---|
| `client.py` | HTTP: change feed, lookup by auction ID, retries |
| `normalize.py` | raw JSON → flat, typed `Lot` |
| `filters.py` | scope (real estate) |
| `storage.py` | SQLite schema, upsert if newer, cursor, `latest_attempts` |
| `history.py` | chain walking and summary |
| `airtable_sync.py` | Airtable rows and upsert |
| `verify.py` | comparison with the primary source |
| `cli.py` | `fetch`, `sync`, `verify` |