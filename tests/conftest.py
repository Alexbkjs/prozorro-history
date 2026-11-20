import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Callable[[str], dict[str, Any]]:
    def _load(auction_id: str) -> dict[str, Any]:
        file_name = FIXTURES_DIR / f"{auction_id}.json"
        with open(file_name, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data

    return _load
