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
2. **The company list is sharded across a 3-day rotation.** Each ATS run touches
   roughly a third of the list, so it finishes well inside the timeout. Every
   company is still checked twice a week.
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

python -m scanner.run --source repos            # fast, no rotation
python -m scanner.run --source ats --shard-of 3
python -m scanner.run --source none             # rebuild board from store only

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
- `--fresh-days` (default 14) — how far back the board looks.
- `--shard-of` — set to 1 to scan every company in one run.
- Update `data/resume_profile.md` when the resume changes; scores recompute on the
  next run.
