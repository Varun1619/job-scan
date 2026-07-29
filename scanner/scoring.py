"""Scores a normalised job record against the candidate profile."""
from __future__ import annotations
import json
import re
from pathlib import Path

from . import profile

# Repo feeds carry an explicit sponsorship field. These values are hard blockers.
SPONSORSHIP_BLOCKERS = {"Does Not Offer Sponsorship", "U.S. Citizenship is Required"}


def load_h1b(path: str | Path) -> dict[str, list]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_") and k != "meta"}


def h1b_for(company: str, table: dict[str, list]) -> dict:
    name = (company or "").lower()
    for key, val in table.items():
        if key in name:
            return {"h1b_total": val[0], "h1b_data_eng": val[1], "h1b_known": True}
    return {"h1b_total": None, "h1b_data_eng": None, "h1b_known": False}


def skill_overlap(text: str, vocab: list[str]) -> tuple[float, list[str]]:
    """Fraction of the vocabulary present in the job text, plus the matched terms."""
    if not text:
        return 0.0, []
    blob = re.sub(r"<[^>]+>", " ", text).lower()
    hits = []
    for term in vocab:
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pattern, blob):
            hits.append(term)
    # 14 matched terms is treated as a saturated match.
    return min(len(hits) / 14.0, 1.0), hits


def missing_keywords(hits: list[str], vocab_core: list[str], limit: int = 8) -> list[str]:
    have = set(hits)
    return [t for t in vocab_core if t not in have][:limit]


def score_job(job: dict, vocab: list[str], h1b_table: dict) -> dict | None:
    """Returns an enriched job dict, or None if the job is filtered out."""
    title = job.get("title", "")
    if profile.excluded(title):
        return None

    fit = profile.role_fit(title)
    if fit < 0.55:
        return None

    location = job.get("location", "")
    if not profile.is_us_location(location):
        return None

    if job.get("sponsorship") in SPONSORSHIP_BLOCKERS:
        return None

    description = job.get("description", "") or ""
    has_desc = len(description) > 200

    if has_desc:
        overlap, hits = skill_overlap(f"{title} {description}", vocab)
    else:
        overlap, hits = skill_overlap(title, vocab)
        # Without a description there is nothing to overlap against; lean on role fit.
        overlap = max(overlap, fit * 0.55)

    sen = profile.seniority_fit(title, description)
    score = 0.55 * overlap + 0.30 * fit + 0.15 * sen

    enriched = dict(job)
    enriched.update(
        {
            "match": round(score * 100),
            "role_fit": fit,
            "seniority_fit": sen,
            "matched_skills": hits[:12],
            "missing_skills": missing_keywords(hits, vocab[:40]) if has_desc else [],
            "scored_on": "description" if has_desc else "title",
        }
    )
    enriched.update(h1b_for(job.get("company", ""), h1b_table))
    enriched.pop("description", None)
    return enriched
