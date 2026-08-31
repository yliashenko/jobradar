"""System clock — one source of "now" that a test can freeze (requirement #2).

The feed's recency filter, the calendar grid and the dedup TTL depend on the
current moment. If everyone reads datetime.now() directly, time can't be fixed
in a test — and checks like "new in 24h" or "current month" become floating.
Here there's a single now(); a test calls freeze(dt) and unfreeze() (an autouse
conftest fixture resets it between tests). The production clock is UTC-aware,
as before.
"""

from __future__ import annotations

from datetime import datetime, timezone

_frozen: datetime | None = None


def freeze(moment: datetime) -> None:
    """Freeze "now" (test). unfreeze() restores the real clock."""
    global _frozen
    _frozen = moment


def unfreeze() -> None:
    global _frozen
    _frozen = None


def now() -> datetime:
    """Current moment, UTC-aware. Frozen in tests via freeze()."""
    return _frozen if _frozen is not None else datetime.now(timezone.utc)
