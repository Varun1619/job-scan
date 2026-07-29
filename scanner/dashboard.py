"""Renders the store into a single self-contained HTML board.

Design note: this is a working tool read at 7am, scanned in under a minute, and
acted on. It borrows the vernacular of a departure board - monospace numerals,
dense rows, a status column - because the job is triage, not browsing. The one
loud element is the run-health strip: if a source failed, the board says so
instead of quietly showing fewer rows.
"""
from __future__ import annotations
import datetime as dt
import html
import json


CSS = """
:root{
  --ink:#14181F; --paper:#FAFAF8; --rule:#E2E1DB; --muted:#6B7280;
  --signal:#0F766E; --visa:#4338CA; --warn:#9A3412; --panel:#FFFFFF;
  --mono:ui-monospace,"SFMono-Regular","JetBrains Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
     font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
.wrap{max-width:1240px;margin:0 auto;padding:28px 20px 80px}

header{display:flex;flex-wrap:wrap;align-items:baseline;gap:18px;
       border-bottom:2px solid var(--ink);padding-bottom:14px}
h1{font-family:var(--mono);font-size:19px;font-weight:600;letter-spacing:-.02em;margin:0}
.countdown{font-family:var(--mono);font-size:12px;color:var(--warn);
           text-transform:uppercase;letter-spacing:.09em}
.stamp{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:auto}

.health{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.chip{font-family:var(--mono);font-size:11px;padding:3px 8px;border:1px solid var(--rule);
      border-radius:2px;background:var(--panel);color:var(--muted);white-space:nowrap}
.chip.ok{border-color:#C8DAD6;color:var(--signal)}
.chip.bad{border-color:#E7C7B8;color:var(--warn);background:#FDF6F2}
.healthnote{font-size:12px;color:var(--muted);margin:6px 0 22px}
.healthnote strong{color:var(--warn);font-weight:600}

.stats{display:flex;flex-wrap:wrap;gap:34px;margin:18px 0 22px}
.stat b{display:block;font-family:var(--mono);font-size:26px;font-weight:600;
        font-variant-numeric:tabular-nums;letter-spacing:-.03em}
.stat span{font-family:var(--mono);font-size:11px;color:var(--muted);
           text-transform:uppercase;letter-spacing:.09em}

.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px}
input[type=search]{font-family:var(--mono);font-size:13px;padding:7px 10px;
  border:1px solid var(--rule);border-radius:2px;background:var(--panel);min-width:220px}
input[type=search]:focus,button:focus-visible{outline:2px solid var(--signal);outline-offset:1px}
button{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  padding:7px 11px;border:1px solid var(--rule);background:var(--panel);color:var(--muted);
  border-radius:2px;cursor:pointer}
button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}

table{width:100%;border-collapse:collapse}
th{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.08em;
   color:var(--muted);text-align:left;padding:8px 10px;border-bottom:1px solid var(--ink);
   cursor:pointer;user-select:none;white-space:nowrap}
td{padding:10px;border-bottom:1px solid var(--rule);vertical-align:top}
tbody tr:hover{background:#F2F3F0}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.match{font-family:var(--mono);font-weight:600;font-variant-numeric:tabular-nums}
.match.hi{color:var(--signal)}
.co{font-weight:600}
.role a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--rule)}
.role a:hover{border-bottom-color:var(--ink)}
.meta{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:3px}
.tag{display:inline-block;font-family:var(--mono);font-size:10px;padding:1px 5px;
     border:1px solid var(--rule);border-radius:2px;margin:2px 3px 0 0;color:var(--muted)}
.tag.visa{border-color:#CBC9F0;color:var(--visa)}
.tag.new{border-color:#C8DAD6;color:var(--signal)}
.empty{padding:44px 10px;color:var(--muted);font-family:var(--mono);font-size:13px}
@media (max-width:720px){
  .hide-sm{display:none} .stats{gap:22px} .wrap{padding:20px 12px 60px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = """
const rows=[...document.querySelectorAll('tbody tr')];
const q=document.getElementById('q');
const filters={strong:false,visa:false,fresh:false,remote:false};
function apply(){
  const term=q.value.toLowerCase().trim();
  let shown=0;
  rows.forEach(r=>{
    const d=r.dataset;
    let ok = !term || r.textContent.toLowerCase().includes(term);
    if(ok&&filters.strong) ok = +d.match>=70;
    if(ok&&filters.visa)   ok = d.visa==='1';
    if(ok&&filters.fresh)  ok = d.fresh==='1';
    if(ok&&filters.remote) ok = d.remote==='1';
    r.hidden=!ok; if(ok) shown++;
  });
  document.getElementById('shown').textContent=shown;
  document.getElementById('nores').hidden = shown>0;
}
q.addEventListener('input',apply);
document.querySelectorAll('button[data-f]').forEach(b=>{
  b.addEventListener('click',()=>{
    const k=b.dataset.f; filters[k]=!filters[k];
    b.setAttribute('aria-pressed',filters[k]); apply();
  });
});
let dir={};
document.querySelectorAll('th[data-k]').forEach(th=>{
  th.addEventListener('click',()=>{
    const k=th.dataset.k; dir[k]=!dir[k]; const s=dir[k]?1:-1;
    const body=document.querySelector('tbody');
    [...body.querySelectorAll('tr')].sort((a,b)=>{
      const x=a.dataset[k], y=b.dataset[k];
      const nx=parseFloat(x), ny=parseFloat(y);
      if(!isNaN(nx)&&!isNaN(ny)) return (nx-ny)*s;
      return String(x).localeCompare(String(y))*s;
    }).forEach(r=>body.appendChild(r));
  });
});
apply();
"""


def _days_to_december() -> int:
    today = dt.date.today()
    target = dt.date(today.year if today.month < 12 else today.year + 1, 12, 1)
    return (target - today).days


def render(state: dict, rows: list[dict], out_path: str, window_label: str = "") -> str:
    e = html.escape
    today = dt.date.today().isoformat()
    recent_runs = state.get("runs", [])[-4:]

    chips, failures = [], []
    for run in recent_runs:
        for name, status in (run.get("per_source") or {}).items():
            good = status.startswith("ok")
            if not good:
                failures.append(name)
            label = name.split("/")[-1][:22]
            chips.append(f'<span class="chip {"ok" if good else "bad"}">{e(label)}</span>')
    chips = chips[-26:]

    if failures:
        note = (
            f'<div class="healthnote"><strong>{len(set(failures))} source(s) did not '
            f"respond on the last run.</strong> Rows below still include everything "
            f"collected on earlier runs, so the board is short, not empty.</div>"
        )
    else:
        note = '<div class="healthnote">All sources responded on the last run.</div>'

    strong = sum(1 for r in rows if r.get("match", 0) >= 70)
    new_today = sum(1 for r in rows if r.get("first_seen") == today)
    sponsors = sum(1 for r in rows if (r.get("h1b_total") or 0) >= 50)

    body = []
    for r in rows:
        m = r.get("match", 0)
        posted = r.get("posted") or r.get("first_seen") or ""
        fresh = posted >= (dt.date.today() - dt.timedelta(days=3)).isoformat()
        remote = "remote" in (r.get("location") or "").lower()
        visa = (r.get("h1b_total") or 0) >= 50
        tags = []
        if r.get("first_seen") == today:
            tags.append('<span class="tag new">new today</span>')
        if visa:
            tags.append(f'<span class="tag visa">H1B {r["h1b_total"]}</span>')
        for s in (r.get("matched_skills") or [])[:4]:
            tags.append(f'<span class="tag">{e(s)}</span>')
        url = r.get("url") or "#"
        body.append(
            f'<tr data-match="{m}" data-company="{e(r.get("company",""))}" '
            f'data-posted="{e(posted)}" data-h1b="{r.get("h1b_total") or 0}" '
            f'data-visa="{int(visa)}" data-fresh="{int(fresh)}" data-remote="{int(remote)}">'
            f'<td class="match {"hi" if m>=70 else ""}">{m}</td>'
            f'<td class="co">{e(r.get("company",""))}</td>'
            f'<td class="role"><a href="{e(url)}" target="_blank" rel="noopener">'
            f'{e(r.get("title",""))}</a><div class="meta">{e(r.get("location") or "—")}'
            f' · {e(r.get("source",""))} · scored on {e(r.get("scored_on","title"))}</div>'
            f"<div>{''.join(tags)}</div></td>"
            f'<td class="num hide-sm">{r.get("h1b_total") or "—"}</td>'
            f'<td class="num hide-sm">{e(posted)}</td></tr>'
        )

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Board — {today}</title><style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>JOB BOARD</h1>
  <div class="countdown">{_days_to_december()} days to december</div>
  <div class="stamp">built {today}{" · " + e(window_label) if window_label else ""}</div>
</header>

<div class="health">{''.join(chips) or '<span class="chip">no runs recorded</span>'}</div>
{note}

<div class="stats">
  <div class="stat"><b id="shown">{len(rows)}</b><span>showing</span></div>
  <div class="stat"><b>{strong}</b><span>strong ≥70</span></div>
  <div class="stat"><b>{new_today}</b><span>new today</span></div>
  <div class="stat"><b>{sponsors}</b><span>known sponsors</span></div>
  <div class="stat"><b>{len(state.get('jobs', {}))}</b><span>in store</span></div>
</div>

<div class="controls">
  <input type="search" id="q" placeholder="filter company, role, skill…" aria-label="Filter rows">
  <button data-f="strong" aria-pressed="false">strong only</button>
  <button data-f="visa" aria-pressed="false">h1b sponsor</button>
  <button data-f="fresh" aria-pressed="false">last 3 days</button>
  <button data-f="remote" aria-pressed="false">remote</button>
</div>

<table>
<thead><tr>
  <th data-k="match">Match</th><th data-k="company">Company</th>
  <th>Role</th><th data-k="h1b" class="num hide-sm">H1B</th>
  <th data-k="posted" class="num hide-sm">Posted</th>
</tr></thead>
<tbody>{''.join(body)}</tbody>
</table>
<div class="empty" id="nores" hidden>Nothing matches that filter. Clear it to see the full board.</div>

</div><script>{JS}</script></body></html>"""

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return out_path


def write_digest(rows: list[dict], path: str, limit: int = 15) -> None:
    """Plain-text digest for the workflow summary / email."""
    today = dt.date.today().isoformat()
    lines = [f"Top {limit} matches — {today}", ""]
    for r in rows[:limit]:
        visa = f" | H1B {r['h1b_total']}" if r.get("h1b_total") else ""
        lines.append(f"{r.get('match',0):>3}  {r.get('company','')} — {r.get('title','')}")
        lines.append(f"     {r.get('location','')}{visa}")
        lines.append(f"     {r.get('url','')}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
