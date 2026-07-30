# job-scanner

A daily job scanner that pulls early-career data roles from two independent
source types, scores them against my resume, attaches H1B sponsorship volume,
and publishes a static board to GitHub Pages. Runs entirely on GitHub Actions —
no server, no API keys, no paid tier.

**Board:** `https://<user>.github.io/job-scanner/`

## Why it exists

An earlier version ran the whole scan in one pass and rendered the board from
whatever that pass returned. When a handful of the fifty-odd company endpoints
timed out, the board came back half empty — and there was no way to tell a slow
hiring week from a broken run.

Three changes fix that:

1. **The board renders from a persistent store, not from a run.** Each scan
   merges into `state/jobs.json`, which is committed back to the repo. A run
   that reaches four sources instead of fifty adds fewer new rows; it cannot
   empty the board.
2. **The company list can be sharded across a rotation.** `--shard-of N` splits
   the list over N days. The workflow defaults to 1 (scan everything daily),
   because a 24-hour window and a multi-day rotation work against each other —
   bump it to 2 or 3 only if runs start timing out.
3. **Failures are visible.** Every run records per-source status. The board
   shows a health strip, and the workflow fails loudly when the success rate
   drops below threshold — so a degraded run sends an email instead of silently
   showing fewer jobs.

## Sources

| Type | Source | Notes |
|---|---|---|
| ATS | Greenhouse / Lever / Ashby | Public JSON boards for the target-company list in `data/ats_map.json`. Sharded 3 ways. |
| Repo | `SimplifyJobs/New-Grad-Positions` | Structured `listings.json`, ~17k listings, has a `sponsorship` field. |
| Repo | `vanshb03/New-Grad-2026` | Same schema. |
| Repo | `jobright-ai/2025-Data-Analysis-New-Grad` | Markdown table, data-specific. |
| Repo | `speedyapply/2026-SWE-College-Jobs` | Markdown table. |

Both workflows write into the same store, so repo postings and target-company
postings appear on one board with one score.

## The freshness window

The board shows the **last 24 hours** of postings. Freshness is measured from
when a role was *posted*, not when the scanner first saw it — otherwise a role
posted ten months ago that a feed surfaced today would count as fresh, and the
board would fill with stale listings inside a week.

Sources differ in precision, and the board says which is which:

| Source | Precision |
|---|---|
| Greenhouse, Lever, Ashby | Full timestamp |
| SimplifyJobs, vanshb03 | Full timestamp (unix epoch) |
| jobright-ai, speedyapply | Date only — pinned to midnight UTC, tagged *day-resolution source* |

Only where a source publishes no date at all does the window fall back to
discovery time. Widen with `--window-hours 48` on a Monday if the weekend was quiet.

## Using the board

- **Window** — 24h / 48h / 3d / 7d. Defaults to 24h; a week of postings is already
  in the page, so widening is instant.
- **Min match** — any / 55+ / 65+ / 70+.
- **Source** — narrow to one feed, e.g. only target-company Greenhouse boards.
- **Toggles** — h1b sponsor (LCA volume ≥ 50), remote, has description. The last one
  matters: rows scored on title alone are noisier than rows scored on a full JD.
- **Search** — matches company, role, location, and matched skills.
- **Apply** — every row has a direct link to the posting. Sort columns by clicking
  the header.
- **Theme** — follows your OS by default; the toggle in the header overrides and
  remembers the choice.

## The board

- **Dark mode.** Follows the system by default; the toggle in the header pins a
  choice and remembers it.
- **All times Eastern.** The zone is `America/New_York`, not a fixed offset, so
  the column header reads EST or EDT correctly through the DST change.
- **Posted column** shows the Eastern date and time; hovering gives the full
  timestamp. Date-only sources show *date only* rather than inventing a time.
- **Apply button** on every row, opening the original posting in a new tab.
- **Filters:** free-text search, source, minimum match (slider), time window,
  and toggles for strong-only, H1B sponsor, under 12h, remote, and
  full-JD-scored. Reset clears everything.

The HTML embeds `--render-hours` of history (default 7 days) while defaulting the
view to `--window-hours` (default 24). Widening the window in the dropdown is
instant and needs no rebuild. The emailed digest stays scoped to the 24-hour
window so the morning list is a shortlist, not a backlog.

## Scoring

`0.55 × skill overlap + 0.30 × role fit + 0.15 × seniority fit`, then filters:

- Titles matching director / principal / staff / manager / architect / intern are dropped.
- Role fit below 0.55 is dropped (see `scanner/profile.py`).
- Non-US locations are dropped.
- `Does Not Offer Sponsorship` and `U.S. Citizenship is Required` are hard blockers
  where the feed exposes that field.
- H1B LCA volume is attached from `data/h1b_fy2025.json` by company-name substring.

ATS compact endpoints have no job description, so those score on title alone and
are marked as such on the board. Descriptions are available from Lever and Ashby.

## Setup

```bash
git clone <repo> && cd job-scanner
pip install -r requirements.txt

python -m scanner.run --source repos                     # fast, no rotation
python -m scanner.run --source ats --shard-of 1
python -m scanner.run --source none --window-hours 48    # rebuild board only

open docs/index.html
```

Then in the repo settings:

- **Settings → Pages → Source: Deploy from branch → `main` / `docs`**
- **Settings → Actions → General → Workflow permissions → Read and write**

Both workflows also have a `workflow_dispatch` trigger, so a manual run is one
click if a scheduled one is skipped. Note that GitHub disables scheduled
workflows on repos with no activity for 60 days — the daily commit from the
scanner keeps it alive on its own.

## Layout

```
scanner/
  profile.py        resume vocabulary, role-fit families, location + seniority rules
  scoring.py        scorer, H1B attachment, sponsorship blockers
  sources_ats.py    Greenhouse/Lever/Ashby fetch, retry, provider fallback, sharding
  sources_repos.py  JSON feeds + markdown table parsers
  store.py          merge, dedupe, prune, run history
  dashboard.py      static HTML board + plain-text digest
  run.py            CLI
data/               resume profile, ATS map, H1B table, company list
state/jobs.json     the store (committed)
docs/index.html     the published board (committed)
```

## Tuning

- `--min-match` (default 45) — raise it to cut noise.
- `--window-hours` (default 24) — the board's default view window.
- `--render-hours` (default 168) — how much history is embedded in the HTML. The
  window control widens through this range client-side, so switching 24h → 7d in
  the browser needs no rebuild.
- `--shard-of` — days to spread the company list over. 1 scans everything daily.
- Update `data/resume_profile.md` when the resume changes; scores recompute on the
  next run.
