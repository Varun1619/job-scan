"""Pulls postings from public company ATS boards (Greenhouse / Lever / Ashby).

Every company is fetched independently and every failure is caught and recorded.
A run that loses half its boards still returns the half that worked.
"""
from __future__ import annotations
import datetime as dt
import json
import time
from pathlib import Path

import requests

TIMEOUT = 25
RETRIES = 3
UA = {"User-Agent": "job-scanner/1.0 (personal job search)"}

ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


def _get(url: str) -> dict | list:
    last = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=UA)
            if r.status_code == 404:
                raise FileNotFoundError(f"404 {url}")
            r.raise_for_status()
            return r.json()
        except FileNotFoundError:
            raise
        except Exception as exc:  # noqa: BLE001 - deliberate catch-all, recorded upstream
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed after {RETRIES} attempts: {last}")


def _norm_greenhouse(company: str, payload: dict) -> list[dict]:
    out = []
    for j in payload.get("jobs", []):
        out.append(
            {
                "company": company,
                "title": j.get("title", ""),
                "location": (j.get("location") or {}).get("name", ""),
                "url": j.get("absolute_url", ""),
                "posted": (j.get("updated_at") or "")[:10],
                "source": "greenhouse",
                "external_id": str(j.get("id", "")),
            }
        )
    return out


def _norm_lever(company: str, payload: list) -> list[dict]:
    out = []
    for j in payload:
        ts = j.get("createdAt")
        posted = dt.datetime.utcfromtimestamp(ts / 1000).date().isoformat() if ts else ""
        out.append(
            {
                "company": company,
                "title": j.get("text", ""),
                "location": (j.get("categories") or {}).get("location", ""),
                "url": j.get("hostedUrl", ""),
                "posted": posted,
                "source": "lever",
                "external_id": str(j.get("id", "")),
                "description": j.get("descriptionPlain", "") or "",
            }
        )
    return out


def _norm_ashby(company: str, payload: dict) -> list[dict]:
    out = []
    for j in payload.get("jobs", []):
        out.append(
            {
                "company": company,
                "title": j.get("title", ""),
                "location": j.get("location", ""),
                "url": j.get("jobUrl", ""),
                "posted": (j.get("publishedAt") or "")[:10],
                "source": "ashby",
                "external_id": str(j.get("id", "")),
                "description": j.get("descriptionPlain", "") or "",
            }
        )
    return out


NORMALISERS = {"greenhouse": _norm_greenhouse, "lever": _norm_lever, "ashby": _norm_ashby}


def fetch_company(company: str, spec: dict) -> tuple[list[dict], str]:
    """Try the mapped provider, then fall back to the other two. Returns (jobs, status)."""
    providers = [spec["ats"]] + [p for p in ENDPOINTS if p != spec["ats"]]
    if spec.get("confirmed"):
        providers = [spec["ats"]]
    errors = []
    for prov in providers:
        try:
            payload = _get(ENDPOINTS[prov].format(slug=spec["slug"]))
            jobs = NORMALISERS[prov](company, payload)
            if jobs:
                return jobs, f"ok:{prov}:{len(jobs)}"
            errors.append(f"{prov}:empty")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{prov}:{type(exc).__name__}")
    return [], "fail:" + ",".join(errors)


def shard_for_today(companies: list[str], of: int) -> list[str]:
    """Split the company list across `of` days so each run stays small and finishes."""
    if of <= 1:
        return companies
    day = dt.date.today().toordinal() % of
    return [c for i, c in enumerate(sorted(companies)) if i % of == day]


def collect(ats_map_path: str | Path, shard_of: int = 1) -> tuple[list[dict], dict]:
    raw = json.loads(Path(ats_map_path).read_text(encoding="utf-8"))
    specs = {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}
    targets = shard_for_today(list(specs), shard_of)

    jobs: list[dict] = []
    report: dict[str, str] = {}
    for company in targets:
        found, status = fetch_company(company, specs[company])
        report[company] = status
        jobs.extend(found)
        time.sleep(0.4)

    ok = sum(1 for s in report.values() if s.startswith("ok"))
    summary = {
        "attempted": len(targets),
        "succeeded": ok,
        "failed": len(targets) - ok,
        "success_rate": round(ok / len(targets), 3) if targets else 0.0,
        "per_company": report,
    }
    return jobs, summary
