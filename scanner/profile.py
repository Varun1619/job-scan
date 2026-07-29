"""Loads the candidate profile: skill vocabulary, role-fit families, seniority rules."""
from __future__ import annotations
import re
from pathlib import Path

# Title families -> fit weight. Order matters: first match wins.
ROLE_FIT = [
    (r"\b(analytics engineer)\b", 1.00),
    (r"\b(data platform|platform engineer)\b", 1.00),
    (r"\bdata engineer(ing)?\b", 1.00),
    (r"\b(bi engineer|business intelligence|bi analyst)\b", 0.92),
    (r"\b(data analyst|reporting analyst|analytics analyst)\b", 0.92),
    (r"\b(ml engineer|machine learning engineer|ai engineer|mlops)\b", 0.85),
    (r"\bdata scientist\b", 0.80),
    (r"\b(software engineer|swe|backend engineer)\b", 0.55),
]

# Titles that are never a fit regardless of keyword overlap.
EXCLUDE_TITLE = re.compile(
    r"\b(director|vice president|\bvp\b|principal|staff|head of|architect|"
    r"manager|lead\b|fellow|intern|internship|co-?op|apprentice|"
    r"sales|account executive|recruiter|marketing|counsel|nurse|clinical)\b",
    re.I,
)

SENIOR_HINT = re.compile(r"\b(senior|sr\.?|iii|iv|\b[5-9]\+? years|\b1[0-9]\+? years)\b", re.I)
JUNIOR_HINT = re.compile(r"\b(new grad|graduate|entry[- ]level|associate|junior|jr\.?|\bi\b|\bii\b|university)\b", re.I)

US_HINT = re.compile(
    r"(united states|\bus\b|\busa\b|remote|hybrid|"
    r"\b(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|"
    r"ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\b)",
    re.I,
)
NON_US = re.compile(
    r"\b(india|canada|toronto|vancouver|london|uk\b|united kingdom|ireland|dublin|germany|berlin|"
    r"munich|france|paris|spain|madrid|barcelona|netherlands|amsterdam|poland|warsaw|krakow|"
    r"singapore|japan|tokyo|australia|sydney|melbourne|brazil|mexico|china|shanghai|beijing|"
    r"israel|tel aviv|switzerland|zurich|sweden|stockholm|romania|bucharest|portugal|lisbon)\b",
    re.I,
)


def load_vocab(path: str | Path) -> list[str]:
    """Pull the canonical skill vocabulary block out of resume_profile.md."""
    text = Path(path).read_text(encoding="utf-8")
    block = re.search(r"## Canonical skill vocabulary.*?\n(.*?)(?=\n##|\Z)", text, re.S)
    if not block:
        return []
    raw = block.group(1).replace("\n", " ")
    terms = {t.strip().lower() for t in raw.split(",") if t.strip()}
    return sorted(terms, key=len, reverse=True)


def role_fit(title: str) -> float:
    t = (title or "").lower()
    for pattern, weight in ROLE_FIT:
        if re.search(pattern, t):
            return weight
    return 0.0


def seniority_fit(title: str, description: str = "") -> float:
    blob = f"{title} {description[:1500]}"
    if JUNIOR_HINT.search(title or ""):
        return 1.0
    if SENIOR_HINT.search(blob):
        return 0.35
    return 0.75


def is_us_location(location: str) -> bool:
    loc = location or ""
    if NON_US.search(loc) and not re.search(r"united states|remote,? us|usa", loc, re.I):
        return False
    return bool(US_HINT.search(loc)) or loc.strip() == ""


def excluded(title: str) -> bool:
    return bool(EXCLUDE_TITLE.search(title or ""))
