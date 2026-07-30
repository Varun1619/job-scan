"""UTC timestamp helpers.

The board runs on a 24-hour window, so every source has to give up a real
timestamp rather than a date. Where a source only publishes a date (the
markdown-table repos), the timestamp is pinned to midnight UTC of that date
and flagged coarse, so a day-granularity source can never masquerade as
minute-accurate freshness.
"""
from __future__ import annotations
import datetime as dt

UTC = dt.timezone.utc


def now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(ts: dt.datetime | None) -> str:
    if ts is None:
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat(timespec="seconds")


def from_epoch(value, millis: bool = False) -> str:
    if not value:
        return ""
    try:
        secs = float(value) / 1000.0 if millis else float(value)
        return iso(dt.datetime.fromtimestamp(secs, UTC))
    except (TypeError, ValueError, OSError):
        return ""


def from_iso(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return iso(dt.datetime.fromisoformat(text))
    except ValueError:
        try:
            return iso(dt.datetime.strptime(text[:10], "%Y-%m-%d"))
        except ValueError:
            return ""


def from_date(value: str) -> str:
    """A bare date becomes midnight UTC. Coarse by definition."""
    if not value:
        return ""
    try:
        return iso(dt.datetime.strptime(str(value)[:10], "%Y-%m-%d"))
    except ValueError:
        return ""


def parse(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def hours_since(value: str) -> float | None:
    ts = parse(value)
    if ts is None:
        return None
    return (now() - ts).total_seconds() / 3600.0


def epoch(value: str) -> int | None:
    """Unix seconds, so the browser can age a row against its own clock."""
    ts = parse(value)
    return int(ts.timestamp()) if ts else None


def age_label(value: str, coarse: bool = False) -> str:
    """'3h', '18h', '2d'. Coarse sources never claim sub-day precision."""
    hrs = hours_since(value)
    if hrs is None:
        return "—"
    if hrs < 0:
        hrs = 0
    if coarse:
        days = int(hrs // 24)
        return "today" if days == 0 else f"{days}d"
    if hrs >= 48:
        return f"{int(hrs // 24)}d"
    if hrs < 1:
        return "<1h"
    return f"{int(hrs)}h"


# --- Eastern time display -------------------------------------------------
# The board is read at 7am in Boston, so every timestamp is shown in Eastern.
# The zone (not a fixed offset) is used so the label flips between EST and EDT
# on its own; a hardcoded -5 would run an hour wrong for most of the year.
try:
    from zoneinfo import ZoneInfo

    EASTERN = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - no tzdata on the host
    EASTERN = dt.timezone(dt.timedelta(hours=-5), "EST")


def to_et(value: str) -> dt.datetime | None:
    ts = parse(value)
    return ts.astimezone(EASTERN) if ts else None


def et_label() -> str:
    """'EST' or 'EDT' for right now."""
    return now().astimezone(EASTERN).strftime("%Z") or "ET"


# %-d and %-I strip the leading zero on glibc but raise ValueError on Windows,
# so the day and hour are formatted by hand and only the locale-stable parts go
# through strftime. Keeps the board buildable on a dev laptop, not just in CI.
def _md(ts: dt.datetime) -> str:
    return f"{ts.strftime('%b')} {ts.day}"


def _hm(ts: dt.datetime) -> str:
    return f"{ts.hour % 12 or 12}:{ts.minute:02d} {ts.strftime('%p')}"


def et_date(value: str) -> str:
    """'Jul 29' — the posted date, Eastern."""
    ts = to_et(value)
    return _md(ts) if ts else "—"


def et_time(value: str) -> str:
    """'3:42 PM', or empty if the value will not parse."""
    ts = to_et(value)
    return _hm(ts) if ts else ""


def et_datetime(value: str, coarse: bool = False) -> str:
    """'Jul 29, 3:42 PM EDT'. Coarse sources get the date only, honestly."""
    ts = to_et(value)
    if not ts:
        return "—"
    if coarse:
        return f"{_md(ts)}, {ts.year} (date only)"
    return f"{_md(ts)}, {ts.year}, {_hm(ts)} " + (ts.strftime("%Z") or "ET")


def et_stamp() -> str:
    ts = now().astimezone(EASTERN)
    return f"{_md(ts)}, {_hm(ts)} " + (ts.strftime("%Z") or "ET")


def from_date_et_end(value: str) -> str:
    """A date-only posting, anchored to the end of that day in Eastern.

    Pinning a bare date to midnight UTC looks tidy but expires the row the
    instant UTC rolls over: at 00:05 UTC every posting dated "today" is
    suddenly 24h old and drops off a 24-hour board. Anchoring to the end of
    the Eastern day (clamped to now, never the future) keeps a same-day
    posting inside the window for the whole day it was actually posted.
    """
    if not value:
        return ""
    try:
        day = dt.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return ""
    end = dt.datetime.combine(day, dt.time(23, 59), tzinfo=EASTERN)
    return iso(min(end, now()))
