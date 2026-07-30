"""Entry point.

  python -m scanner.run --source ats   --shard-of 3
  python -m scanner.run --source repos
  python -m scanner.run --source none          # rebuild the board from the store only
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import dashboard, scoring, sources_ats, sources_repos, store

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATE = ROOT / "state" / "jobs.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["ats", "repos", "none"], default="ats")
    ap.add_argument("--shard-of", type=int, default=1,
                    help="Split the company list across N days so each run finishes.")
    ap.add_argument("--window-hours", type=int, default=24,
                    help="Default view window on the board, in hours.")
    ap.add_argument("--render-hours", type=int, default=168,
                    help="How much history to embed in the HTML so the window "
                         "control can widen client-side without a rebuild.")
    ap.add_argument("--min-match", type=int, default=45)
    ap.add_argument("--out", default=str(ROOT / "docs" / "index.html"))
    ap.add_argument("--fail-under", type=float, default=0.6,
                    help="Exit non-zero if the source success rate drops below this.")
    args = ap.parse_args(argv)

    vocab = __import__("scanner.profile", fromlist=["x"]).load_vocab(DATA / "resume_profile.md")
    h1b = scoring.load_h1b(DATA / "h1b_fy2025.json")
    state = store.load(STATE)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M")

    # merge() only refreshes timestamps and match, so H1B labels written by an
    # older table (or an older matching rule) would otherwise live in the store
    # forever. Re-annotate every row on every run instead.
    for job in state["jobs"].values():
        job.update(scoring.h1b_for(job.get("company", ""), h1b))

    summary = {"attempted": 0, "succeeded": 0, "failed": 0, "success_rate": 1.0, "per_company": {}}
    new_count = 0

    if args.source != "none":
        if args.source == "ats":
            raw, summary = sources_ats.collect(DATA / "ats_map.json", shard_of=args.shard_of)
        else:
            raw, summary = sources_repos.collect()

        scored = [s for s in (scoring.score_job(j, vocab, h1b) for j in raw) if s]
        new_count = store.merge(state, scored, run_id)
        store.record_run(state, run_id, args.source, summary, new_count)
        pruned = store.prune(state)
        store.save(STATE, state)
        print(f"[{args.source}] raw={len(raw)} scored={len(scored)} new={new_count} pruned={pruned}")
        print(f"[{args.source}] sources ok={summary['succeeded']}/{summary['attempted']}")
        for name, status in summary["per_company"].items():
            if not status.startswith("ok"):
                print(f"  ! {name}: {status}", file=sys.stderr)

    render_hours = max(args.render_hours, args.window_hours)
    rows = store.board_rows(state, window_hours=render_hours, min_match=args.min_match)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dashboard.render(state, rows, str(out),
                     window_label=f"default view: last {args.window_hours}h",
                     default_hours=args.window_hours)
    dashboard.write_digest(rows, str(out.parent / "digest.txt"),
                           window_hours=args.window_hours)
    print(f"board: {out} ({len(rows)} rows, {len(state['jobs'])} in store)")

    Path(ROOT / "state" / "last_run.json").write_text(
        json.dumps({"run_id": run_id, "source": args.source, "new": new_count, **summary}, indent=1),
        encoding="utf-8",
    )

    if summary["attempted"] and summary["success_rate"] < args.fail_under:
        print(f"::warning::source success rate {summary['success_rate']:.0%} below threshold")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
