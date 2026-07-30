"""Persistent job store.

The board is rendered from this store, never from a single run's output.
That is the whole point: a run that only reaches half its sources adds fewer
new rows instead of producing a half-empty board.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from . import timeutil


def job_key(job: dict) -> str:
    url = re.sub(r"[?#].*$", "", (job.get("url") or "").lower().rstrip("/"))
    ident = job.get("external_id") or url
    raw = f"{job.get('company','').lower().strip()}|{job.get('title','').lower().strip()}|{ident}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def load(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"jobs": {}, "runs": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def merge(state: dict, jobs: list[dict], run_id: str) -> int:
    """Adds jobs to the store. Returns how many were genuinely new."""
    stamp = timeutil.iso(timeutil.now())
    new = 0
    for job in jobs:
        key = job_key(job)
        existing = state["jobs"].get(key)
        if existing:
            existing["last_seen_ts"] = stamp
            existing["match"] = job.get("match", existing.get("match"))
            # Refresh the posted timestamp: coarse sources re-anchor as the day advances.
            if job.get("posted_ts"):
                existing["posted_ts"] = job["posted_ts"]
                existing["posted_coarse"] = job.get("posted_coarse", False)
            # Backfill records written before the switch to timestamps.
            existing.setdefault("first_seen_ts", timeutil.from_date(existing.get("first_seen", "")))
            existing.setdefault("posted_ts", timeutil.from_date(existing.get("posted", "")))
            continue
        record = dict(job)
        record["first_seen_ts"] = stamp
        record["last_seen_ts"] = stamp
        record["found_in_run"] = run_id
        record.setdefault("status", "new")
        state["jobs"][key] = record
        new += 1
    return new


def prune(state: dict, keep_days: int = 45) -> int:
    """Drops rows not seen in a while. Anything marked applied/saved is kept."""
    limit = keep_days * 24
    doomed = []
    for k, v in state["jobs"].items():
        if v.get("status") not in (None, "new", "seen"):
            continue
        age = timeutil.hours_since(v.get("last_seen_ts") or timeutil.from_date(v.get("last_seen", "")))
        if age is not None and age > limit:
            doomed.append(k)
    for k in doomed:
        del state["jobs"][k]
    return len(doomed)


def record_run(state: dict, run_id: str, source: str, summary: dict, new_count: int) -> None:
    state.setdefault("runs", [])
    state["runs"].append(
        {
            "run_id": run_id,
            "source": source,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "new_jobs": new_count,
            **{k: v for k, v in summary.items() if k != "per_company"},
            "per_source": summary.get("per_company", {}),
        }
    )
    state["runs"] = state["runs"][-30:]


def freshness(job: dict) -> float | None:
    """Hours since the posting went up.

    Falls back to when the scanner first saw it only when the source published
    no date at all. Deliberately not the more-recent of the two: a role posted
    ten months ago that a feed surfaced today is not a 24-hour-old posting, and
    letting discovery time stand in for post time is how a "last 24 hours" board
    quietly fills up with stale listings.
    """
    posted = timeutil.hours_since(job.get("posted_ts") or "")
    if posted is not None:
        return posted
    return timeutil.hours_since(job.get("first_seen_ts") or "")


def board_rows(state: dict, window_hours: int = 24, min_match: int = 0) -> list[dict]:
    rows = []
    for job in state["jobs"].values():
        if job.get("match", 0) < min_match:
            continue
        age = freshness(job)
        if age is None or age > window_hours:
            continue
        enriched = dict(job)
        enriched["age_hours"] = round(age, 1)
        rows.append(enriched)
    rows.sort(key=lambda r: (-r.get("match", 0), r.get("age_hours", 9e9)))
    return rows
