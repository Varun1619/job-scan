"""Renders the store into a single self-contained HTML board.

Design note: this is a working tool read at 7am, scanned in under a minute, and
acted on. It borrows the vernacular of a departure board - monospace numerals,
dense rows, a status column - because the job is triage, not browsing. The one
loud element is the run-health strip: if a source failed, the board says so
instead of quietly showing fewer rows.

All times are Eastern. Theme follows the system by default and can be pinned.
"""
from __future__ import annotations
import html

from . import timeutil

CSS = """
:root{
  --paper:#FAFAF8; --panel:#FFFFFF; --ink:#14181F; --muted:#6B7280;
  --rule:#E2E1DB; --signal:#0F766E; --visa:#4338CA; --warn:#9A3412;
  --hover:#F2F3F0; --btn-ink:#FAFAF8; --tag-visa-b:#CBC9F0; --tag-ok-b:#C8DAD6;
  --bad-bg:#FDF6F2; --bad-b:#E7C7B8;
  --mono:ui-monospace,"SFMono-Regular","JetBrains Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
[data-theme="dark"]{
  --paper:#101319; --panel:#171B22; --ink:#E7E5E0; --muted:#8B93A1;
  --rule:#272D37; --signal:#2DD4BF; --visa:#A5B4FC; --warn:#FB923C;
  --hover:#1D222B; --btn-ink:#101319; --tag-visa-b:#3B3F66; --tag-ok-b:#1F4B47;
  --bad-bg:#231A16; --bad-b:#5A3A2A;
}
*{box-sizing:border-box}
html{color-scheme:light}
[data-theme="dark"]{color-scheme:dark}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
     font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
.wrap{max-width:1320px;margin:0 auto;padding:28px 20px 80px}

header{display:flex;flex-wrap:wrap;align-items:baseline;gap:16px;
       border-bottom:2px solid var(--ink);padding-bottom:14px}
h1{font-family:var(--mono);font-size:19px;font-weight:600;letter-spacing:-.02em;margin:0}
.countdown{font-family:var(--mono);font-size:12px;color:var(--warn);
           text-transform:uppercase;letter-spacing:.09em}
.stamp{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:auto}
#theme{margin-left:8px}

.health{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.chip{font-family:var(--mono);font-size:11px;padding:3px 8px;border:1px solid var(--rule);
      border-radius:2px;background:var(--panel);color:var(--muted);white-space:nowrap}
.chip.ok{border-color:var(--tag-ok-b);color:var(--signal)}
.chip.bad{border-color:var(--bad-b);color:var(--warn);background:var(--bad-bg)}
.healthnote{font-size:12px;color:var(--muted);margin:6px 0 22px}
.healthnote strong{color:var(--warn);font-weight:600}

.stats{display:flex;flex-wrap:wrap;gap:34px;margin:18px 0 22px}
.stat b{display:block;font-family:var(--mono);font-size:26px;font-weight:600;
        font-variant-numeric:tabular-nums;letter-spacing:-.03em}
.stat span{font-family:var(--mono);font-size:11px;color:var(--muted);
           text-transform:uppercase;letter-spacing:.09em}

.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.controls.second{margin-bottom:16px}
input[type=search],select{font-family:var(--mono);font-size:13px;padding:7px 10px;
  border:1px solid var(--rule);border-radius:2px;background:var(--panel);
  color:var(--ink);min-width:150px}
input[type=search]{min-width:230px}
input[type=search]:focus,select:focus,button:focus-visible,a:focus-visible{
  outline:2px solid var(--signal);outline-offset:1px}
button{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  padding:7px 11px;border:1px solid var(--rule);background:var(--panel);color:var(--muted);
  border-radius:2px;cursor:pointer}
button:hover{border-color:var(--muted)}
button[aria-pressed=true]{background:var(--ink);color:var(--btn-ink);border-color:var(--ink)}
.slider{display:flex;align-items:center;gap:8px;font-family:var(--mono);
        font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
input[type=range]{accent-color:var(--signal);width:110px}

table{width:100%;border-collapse:collapse}
th{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.08em;
   color:var(--muted);text-align:left;padding:8px 10px;border-bottom:1px solid var(--ink);
   cursor:pointer;user-select:none;white-space:nowrap}
th.plain{cursor:default}
td{padding:10px;border-bottom:1px solid var(--rule);vertical-align:top}
tbody tr:hover{background:var(--hover)}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.date{font-family:var(--mono);font-size:12px;white-space:nowrap}
.date small{display:block;color:var(--muted);font-size:11px}
.match{font-family:var(--mono);font-weight:600;font-variant-numeric:tabular-nums}
.match.hi{color:var(--signal)}
.co{font-weight:600}
.role strong{font-weight:600;display:block}
.meta{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:3px}
.tag{display:inline-block;font-family:var(--mono);font-size:10px;padding:1px 5px;
     border:1px solid var(--rule);border-radius:2px;margin:4px 3px 0 0;color:var(--muted)}
.tag.visa{border-color:var(--tag-visa-b);color:var(--visa)}
.apply{display:inline-block;font-family:var(--mono);font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;padding:7px 13px;border:1px solid var(--ink);border-radius:2px;
  background:var(--ink);color:var(--btn-ink);text-decoration:none;white-space:nowrap}
.apply:hover{background:var(--signal);border-color:var(--signal)}
.empty{padding:44px 10px;color:var(--muted);font-family:var(--mono);font-size:13px}
@media (max-width:860px){
  .hide-sm{display:none} .stats{gap:22px} .wrap{padding:20px 12px 60px}
  input[type=search]{min-width:100%}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = """
(function(){
  var root=document.documentElement, btn=document.getElementById('theme');
  function store(v){try{localStorage.setItem('board-theme',v)}catch(e){}}
  function read(){try{return localStorage.getItem('board-theme')}catch(e){return null}}
  function set(t){
    root.setAttribute('data-theme',t);
    btn.textContent = t==='dark' ? 'light' : 'dark';
    btn.setAttribute('aria-label','Switch to '+(t==='dark'?'light':'dark')+' theme');
  }
  var saved=read();
  set(saved || (window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  btn.addEventListener('click',function(){
    var next = root.getAttribute('data-theme')==='dark' ? 'light' : 'dark';
    set(next); store(next);
  });
})();

var rows=[].slice.call(document.querySelectorAll('tbody tr'));
var q=document.getElementById('q'), src=document.getElementById('src'),
    min=document.getElementById('min'), minv=document.getElementById('minv'),
    win=document.getElementById('win'), defaultWin=win.value;
var toggles={strong:false,visa:false,half:false,remote:false,desc:false};

// Age is recomputed from the posting timestamp on every pass rather than read
// off data-age. The board is a static file: trusting the age baked in at build
// time is how a three-day-old page keeps showing rows as "5h" and lets them sit
// inside a 24-hour window. data-age survives only as a fallback for a row whose
// source published no parseable timestamp, and as the sort key (every row is
// offset by the same delta, so the ordering still holds).
function ageOf(d,now){
  var ts=+d.ts;
  return ts ? (now - ts*1000)/3600000 : +d.age;
}
function fmtAge(h,coarse){
  if(h<0) h=0;
  if(coarse){ var d=Math.floor(h/24); return d===0?'today':d+'d'; }
  if(h>=48) return Math.floor(h/24)+'d';
  if(h<1)   return '<1h';
  return Math.floor(h)+'h';
}

function apply(){
  var term=q.value.toLowerCase().trim(), source=src.value, floor=+min.value,
      hours=+win.value, now=Date.now(),
      shown=0, nstrong=0, nhalf=0, nsponsors=0;
  minv.textContent=floor;
  rows.forEach(function(r){
    var d=r.dataset, age=ageOf(d,now), cell=r.querySelector('.agecell');
    if(cell) cell.textContent=fmtAge(age,d.coarse==='1');
    var ok = age <= hours;
    if(ok && term)   ok = r.textContent.toLowerCase().indexOf(term)>-1;
    if(ok && source!=='all') ok = d.source===source;
    if(ok) ok = +d.match >= floor;
    if(ok && toggles.strong) ok = +d.match>=70;
    if(ok && toggles.visa)   ok = d.visa==='1';
    if(ok && toggles.half)   ok = age<=12;
    if(ok && toggles.remote) ok = d.remote==='1';
    if(ok && toggles.desc)   ok = d.desc==='1';
    r.hidden=!ok;
    if(ok){
      shown++;
      if(+d.match>=70) nstrong++;
      if(age<=12)      nhalf++;
      if(+d.h1b>=50)   nsponsors++;
    }
  });
  document.getElementById('shown').textContent=shown;
  document.getElementById('nstrong').textContent=nstrong;
  document.getElementById('nhalf').textContent=nhalf;
  document.getElementById('nsponsors').textContent=nsponsors;
  document.getElementById('nores').hidden = shown>0;
}
q.addEventListener('input',apply);
src.addEventListener('change',apply);
win.addEventListener('change',apply);
min.addEventListener('input',apply);
document.querySelectorAll('button[data-f]').forEach(function(b){
  b.addEventListener('click',function(){
    var k=b.dataset.f; toggles[k]=!toggles[k];
    b.setAttribute('aria-pressed',toggles[k]); apply();
  });
});
document.getElementById('clear').addEventListener('click',function(){
  q.value=''; src.value='all'; min.value=0; win.value=defaultWin;
  Object.keys(toggles).forEach(function(k){toggles[k]=false});
  document.querySelectorAll('button[data-f]').forEach(function(b){
    b.setAttribute('aria-pressed','false')});
  apply();
});
var dir={};
document.querySelectorAll('th[data-k]').forEach(function(th){
  th.addEventListener('click',function(){
    var k=th.dataset.k; dir[k]=!dir[k]; var s=dir[k]?1:-1;
    var body=document.querySelector('tbody');
    [].slice.call(body.querySelectorAll('tr')).sort(function(a,b){
      var x=a.dataset[k], y=b.dataset[k];
      var nx=parseFloat(x), ny=parseFloat(y);
      if(!isNaN(nx)&&!isNaN(ny)) return (nx-ny)*s;
      return String(x).localeCompare(String(y))*s;
    }).forEach(function(r){body.appendChild(r)});
  });
});
apply();
"""


def _days_to_december() -> int:
    import datetime as dt

    today = timeutil.now().astimezone(timeutil.EASTERN).date()
    target = dt.date(today.year if today.month < 12 else today.year + 1, 12, 1)
    return (target - today).days


def render(state: dict, rows: list[dict], out_path: str, window_label: str = "",
           default_hours: int = 24) -> str:
    e = html.escape
    recent_runs = state.get("runs", [])[-4:]

    chips, failures = [], []
    for run in recent_runs:
        for name, status in (run.get("per_source") or {}).items():
            good = status.startswith("ok")
            if not good:
                failures.append(name)
            chips.append(
                f'<span class="chip {"ok" if good else "bad"}">{e(name.split("/")[-1][:22])}</span>'
            )
    chips = chips[-26:]

    if failures:
        note = (
            f'<div class="healthnote"><strong>{len(set(failures))} source(s) did not '
            f"respond on the last run.</strong> Rows below still include everything "
            f"collected on earlier runs, so the board is short, not empty.</div>"
        )
    else:
        note = '<div class="healthnote">All sources responded on the last run.</div>'

    in_window = [r for r in rows if r.get("age_hours", 9e9) <= default_hours]
    strong = sum(1 for r in in_window if r.get("match", 0) >= 70)
    very_fresh = sum(1 for r in in_window if r.get("age_hours", 999) <= 12)
    sponsors = sum(1 for r in in_window if (r.get("h1b_total") or 0) >= 50)
    widest = max((r.get("age_hours", 0) for r in rows), default=default_hours)
    sources = sorted({r.get("source", "") for r in rows if r.get("source")})

    body = []
    for r in rows:
        m = r.get("match", 0)
        coarse = bool(r.get("posted_coarse"))
        age_h = r.get("age_hours", 999)
        ts = r.get("posted_ts") or r.get("first_seen_ts") or ""
        age = timeutil.age_label(ts, coarse)
        posted_date = timeutil.et_date(ts)
        posted_full = timeutil.et_datetime(ts, coarse)
        posted_time = "" if coarse else timeutil.et_time(ts)
        remote = "remote" in (r.get("location") or "").lower()
        visa = (r.get("h1b_total") or 0) >= 50
        has_desc = r.get("scored_on") == "description"

        tags = []
        if visa:
            tags.append(f'<span class="tag visa">H1B {r["h1b_total"]}</span>')
        if coarse:
            tags.append('<span class="tag">day-resolution source</span>')
        for skill in (r.get("matched_skills") or [])[:4]:
            tags.append(f'<span class="tag">{e(skill)}</span>')

        url = r.get("url") or ""
        apply_cell = (
            f'<a class="apply" href="{e(url)}" target="_blank" rel="noopener">Apply</a>'
            if url
            else '<span class="meta">no link</span>'
        )
        body.append(
            f'<tr data-match="{m}" data-company="{e(r.get("company",""))}" '
            f'data-age="{age_h}" data-ts="{timeutil.epoch(ts) or ""}" '
            f'data-coarse="{int(coarse)}" data-h1b="{r.get("h1b_total") or 0}" '
            f'data-source="{e(r.get("source",""))}" data-desc="{int(has_desc)}" '
            f'data-visa="{int(visa)}" data-remote="{int(remote)}"'
            f'{" hidden" if age_h > default_hours else ""}>'
            f'<td class="match {"hi" if m >= 70 else ""}">{m}</td>'
            f'<td class="co">{e(r.get("company",""))}</td>'
            f'<td class="role"><strong>{e(r.get("title",""))}</strong>'
            f'<div class="meta">{e(r.get("location") or "—")} · {e(r.get("source",""))}'
            f' · scored on {e(r.get("scored_on","title"))}</div>'
            f'<div>{"".join(tags)}</div></td>'
            f'<td class="num hide-sm">{r.get("h1b_total") or "—"}</td>'
            f'<td class="date" title="{e(posted_full)}">{e(posted_date)}'
            f'{f"<small>{e(posted_time)}</small>" if posted_time else "<small>date only</small>"}</td>'
            f'<td class="num agecell">{e(age)}</td>'
            f"<td>{apply_cell}</td></tr>"
        )

    opts = "".join(f'<option value="{e(s)}">{e(s)}</option>' for s in sources)
    choices = [h for h in (12, 24, 48, 72, 168) if h <= max(widest, default_hours) or h == default_hours]
    if default_hours not in choices:
        choices.append(default_hours)
    win_opts = "".join(
        f'<option value="{h}"{" selected" if h == default_hours else ""}>'
        f'{"last " + str(h) + "h" if h < 48 else "last " + str(h // 24) + "d"}</option>'
        for h in sorted(set(choices))
    )
    tz = timeutil.et_label()

    doc = f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Board</title><style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>JOB BOARD</h1>
  <div class="countdown">{_days_to_december()} days to december</div>
  <div class="stamp">built {e(timeutil.et_stamp())}{" · " + e(window_label) if window_label else ""}
    <button id="theme" aria-label="Switch theme">dark</button></div>
</header>

<div class="health">{''.join(chips) or '<span class="chip">no runs recorded</span>'}</div>
{note}

<div class="stats">
  <div class="stat"><b id="shown">{len(in_window)}</b><span>showing</span></div>
  <div class="stat"><b id="nstrong">{strong}</b><span>strong &ge;70</span></div>
  <div class="stat"><b id="nhalf">{very_fresh}</b><span>under 12h</span></div>
  <div class="stat"><b id="nsponsors">{sponsors}</b><span>known sponsors</span></div>
  <div class="stat"><b>{len(state.get('jobs', {}))}</b><span>in store</span></div>
</div>

<div class="controls">
  <input type="search" id="q" placeholder="filter company, role, skill&hellip;" aria-label="Filter rows">
  <select id="win" aria-label="Time window">{win_opts}</select>
  <select id="src" aria-label="Filter by source"><option value="all">all sources</option>{opts}</select>
  <label class="slider">min match
    <input type="range" id="min" min="0" max="90" step="5" value="0" aria-label="Minimum match score">
    <span id="minv">0</span></label>
</div>
<div class="controls second">
  <button data-f="strong" aria-pressed="false">strong only</button>
  <button data-f="visa" aria-pressed="false">h1b sponsor</button>
  <button data-f="half" aria-pressed="false">under 12h</button>
  <button data-f="remote" aria-pressed="false">remote</button>
  <button data-f="desc" aria-pressed="false">full jd scored</button>
  <button id="clear">reset</button>
</div>

<table>
<thead><tr>
  <th data-k="match">Match</th>
  <th data-k="company">Company</th>
  <th class="plain">Role</th>
  <th data-k="h1b" class="num hide-sm">H1B</th>
  <th data-k="age" class="date">Posted ({e(tz)})</th>
  <th data-k="age" class="num">Age</th>
  <th class="plain">Apply</th>
</tr></thead>
<tbody>{''.join(body)}</tbody>
</table>
<div class="empty" id="nores" hidden>Nothing matches those filters. Try reset, or widen the time window above.</div>

</div><script>{JS}</script></body></html>"""

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return out_path


def write_digest(rows: list[dict], path: str, limit: int = 15, window_hours: int = 24) -> None:
    """Plain-text digest for the workflow summary / email.

    Scoped to the default window even though the HTML embeds more history, so the
    morning email is a day's shortlist rather than a week's backlog.
    """
    rows = [r for r in rows if r.get("age_hours", 9e9) <= window_hours]
    lines = [f"Top {min(limit, len(rows))} of {len(rows)} — last {window_hours}h — {timeutil.et_stamp()}", ""]
    if not rows:
        lines.append("Nothing new in the window. Check state/last_run.json if that looks wrong.")
    for r in rows[:limit]:
        visa = f" | H1B {r['h1b_total']}" if r.get("h1b_total") else ""
        ts = r.get("posted_ts") or r.get("first_seen_ts") or ""
        coarse = bool(r.get("posted_coarse"))
        lines.append(
            f"{r.get('match',0):>3}  [{timeutil.age_label(ts, coarse):>5}]  "
            f"{r.get('company','')} — {r.get('title','')}"
        )
        lines.append(f"            posted {timeutil.et_datetime(ts, coarse)}")
        lines.append(f"            {r.get('location','')}{visa}")
        lines.append(f"            {r.get('url','')}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
