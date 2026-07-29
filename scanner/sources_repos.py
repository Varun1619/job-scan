"""Pulls postings from community-maintained GitHub job repos.

Two shapes are supported:
  * JSON feeds  - SimplifyJobs-style listings.json (best: structured + sponsorship field)
  * MD tables   - README.md markdown tables (jobright-ai, speedyapply)
"""
from __future__ import annotations
import datetime as dt
import html
import re
import time

import requests

TIMEOUT = 40
RETRIES = 3
UA = {"User-Agent": "job-scanner/1.0 (personal job search)"}

JSON_FEEDS = [
    {
        "name": "SimplifyJobs/New-Grad-Positions",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
        "categories": {"AI/ML/Data", "Software", "Data Science, AI & Machine Learning", "Software Engineering"},
    },
    {
        "name": "vanshb03/New-Grad-2026",
        "url": "https://raw.githubusercontent.com/vanshb03/New-Grad-2026/dev/.github/scripts/listings.json",
        "categories": None,
    },
]

MD_FEEDS = [
    {
        "name": "jobright-ai/Data-Analysis-New-Grad",
        "url": "https://raw.githubusercontent.com/jobright-ai/2025-Data-Analysis-New-Grad/master/README.md",
        "cols": {"company": 0, "title": 1, "location": 2, "posted": 4},
    },
    {
        "name": "speedyapply/2026-SWE-College-Jobs",
        "url": "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/README.md",
        "cols": {"company": 0, "title": 1, "location": 2, "posted": 5},
    },
]

LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
HREF = re.compile(r'href="(https?://[^"]+)"')
TAGS = re.compile(r"<[^>]+>")
BOLD = re.compile(r"\*\*")


def _get_text(url: str) -> str:
    last = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=UA)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed after {RETRIES} attempts: {last}")


def _clean(cell: str) -> str:
    txt = LINK.sub(r"\1", cell)
    txt = TAGS.sub(" ", txt)
    txt = BOLD.sub("", txt)
    return html.unescape(re.sub(r"\s+", " ", txt)).strip(" |")


def _first_url(cell: str) -> str:
    m = LINK.search(cell) or HREF.search(cell)
    if not m:
        return ""
    return m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)


def _parse_age(cell: str) -> str:
    """Repo READMEs use 'Jul 24' or '23d'. Normalise both to an ISO date."""
    cell = _clean(cell)
    m = re.match(r"(\d+)\s*d", cell)
    if m:
        return (dt.date.today() - dt.timedelta(days=int(m.group(1)))).isoformat()
    m = re.match(r"([A-Za-z]{3})\s+(\d{1,2})", cell)
    if m:
        try:
            today = dt.date.today()
            parsed = dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%b %d %Y").date()
            if parsed > today:  # posting is from last year
                parsed = parsed.replace(year=today.year - 1)
            return parsed.isoformat()
        except ValueError:
            return ""
    return ""


def from_json_feed(feed: dict) -> list[dict]:
    payload = requests.get(feed["url"], timeout=TIMEOUT, headers=UA).json()
    out = []
    for j in payload:
        if not j.get("active") or not j.get("is_visible", True):
            continue
        if feed["categories"] and j.get("category") not in feed["categories"]:
            continue
        posted = ""
        if j.get("date_posted"):
            posted = dt.datetime.utcfromtimestamp(j["date_posted"]).date().isoformat()
        out.append(
            {
                "company": j.get("company_name", ""),
                "title": j.get("title", ""),
                "location": ", ".join(j.get("locations") or []),
                "url": j.get("url", ""),
                "posted": posted,
                "source": feed["name"],
                "external_id": str(j.get("id", "")),
                "sponsorship": j.get("sponsorship"),
            }
        )
    return out


def from_md_feed(feed: dict) -> list[dict]:
    text = _get_text(feed["url"])
    cols = feed["cols"]
    out = []
    for line in text.splitlines():
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = line.split("|")[1:-1]
        if len(cells) <= max(cols.values()):
            continue
        title_cell = cells[cols["title"]]
        company = _clean(cells[cols["company"]])
        title = _clean(title_cell)
        if not company or not title or company.lower() in {"company", "↳"}:
            continue
        out.append(
            {
                "company": company,
                "title": title,
                "location": _clean(cells[cols["location"]]),
                "url": _first_url(title_cell) or _first_url(line),
                "posted": _parse_age(cells[cols["posted"]]),
                "source": feed["name"],
                "external_id": "",
            }
        )
    return out


def collect() -> tuple[list[dict], dict]:
    jobs: list[dict] = []
    report: dict[str, str] = {}

    for feed in JSON_FEEDS:
        try:
            found = from_json_feed(feed)
            jobs.extend(found)
            report[feed["name"]] = f"ok:{len(found)}"
        except Exception as exc:  # noqa: BLE001
            report[feed["name"]] = f"fail:{type(exc).__name__}"

    for feed in MD_FEEDS:
        try:
            found = from_md_feed(feed)
            jobs.extend(found)
            report[feed["name"]] = f"ok:{len(found)}"
        except Exception as exc:  # noqa: BLE001
            report[feed["name"]] = f"fail:{type(exc).__name__}"

    ok = sum(1 for s in report.values() if s.startswith("ok"))
    total = len(report)
    summary = {
        "attempted": total,
        "succeeded": ok,
        "failed": total - ok,
        "success_rate": round(ok / total, 3) if total else 0.0,
        "per_company": report,
    }
    return jobs, summary
