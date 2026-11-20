"""Scope filters: decide which normalized lots we keep."""

from prozorro_history.normalize import Lot

# CAV is the classifier for what is being sold. Its first two digits are the
# top-level category, and "04" is the real-estate branch.
REAL_ESTATE_CAV_PREFIX = "04"


def is_real_estate(lot: Lot) -> bool:
    """Return True if the lot's CAV code is in the real-estate branch ("04...").

    The rule is deliberately simple: a plain prefix check on the CAV code. A
    lot without a CAV code is not real estate.

    Known limitations:
    - Land plots (CAV "06...", e.g. agricultural land) are excluded, because
      they are not under "04". Whether land should be in scope is a question
      for the project owner.
    - Real-estate lots filed under another branch are missed, e.g. CAV
      "70123200-1" ("Sale of non-residential estate").
    """
    return (lot.cav_code or "").startswith(REAL_ESTATE_CAV_PREFIX)
