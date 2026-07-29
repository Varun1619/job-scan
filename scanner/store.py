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
    today = dt.date.today().isoformat()
    new = 0
    for job in jobs:
        key = job_key(job)
        existing = state["jobs"].get(key)
        if existing:
            existing["last_seen"] = today
            existing["match"] = job.get("match", existing.get("match"))
            continue
        record = dict(job)
        record["first_seen"] = today
        record["last_seen"] = today
        record["found_in_run"] = run_id
        record.setdefault("status", "new")
        state["jobs"][key] = record
        new += 1
    return new


def prune(state: dict, keep_days: int = 45) -> int:
    """Drops rows not seen in a while. Anything marked applied/saved is kept."""
    cutoff = (dt.date.today() - dt.timedelta(days=keep_days)).isoformat()
    doomed = [
        k
        for k, v in state["jobs"].items()
        if v.get("last_seen", "") < cutoff and v.get("status") in (None, "new", "seen")
    ]
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


def board_rows(state: dict, fresh_days: int = 14, min_match: int = 0) -> list[dict]:
    cutoff = (dt.date.today() - dt.timedelta(days=fresh_days)).isoformat()
    rows = [
        v
        for v in state["jobs"].values()
        if (v.get("posted") or v.get("first_seen", "")) >= cutoff and v.get("match", 0) >= min_match
    ]
    rows.sort(key=lambda r: (-r.get("match", 0), r.get("posted") or ""), reverse=False)
    rows.sort(key=lambda r: r.get("match", 0), reverse=True)
    return rows
