"""Cleanup rules applied before anything else touches a lead.

Most routing bugs I have seen come from dirty inputs: a domain with
"https://www." in front, a title typed in caps, a state spelled out.
Normalizing first keeps the scoring and dedupe code simple.
"""
from __future__ import annotations

import re

FREE_MAIL = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "proton.me", "protonmail.com", "live.com", "msn.com",
}

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC",
}

COMPANY_SUFFIXES = re.compile(
    r"[,\.]?\s+(inc|inc\.|llc|l\.l\.c\.|ltd|co|corp|corporation|company|pbc)\.?$",
    re.IGNORECASE,
)

# Order matters: first match wins.
SENIORITY_RULES = [
    ("c_level", r"\b(chief|ceo|coo|cfo|cro|cmo|cto|founder|co-founder|owner|president)\b"),
    ("vp", r"\b(vp|vice president|svp|evp)\b"),
    ("head", r"\bhead of\b"),
    ("director", r"\bdirector\b"),
    ("manager", r"\b(manager|lead)\b"),
    ("ic", r".*"),
]


def clean_domain(value: str) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"^[a-z]+://", "", v)
    v = v.split("/")[0].split("?")[0]
    if v.startswith("www."):
        v = v[4:]
    return v


def domain_from_email(email: str) -> str:
    if "@" not in (email or ""):
        return ""
    return clean_domain(email.split("@", 1)[1])


def is_free_mail(domain: str) -> bool:
    return clean_domain(domain) in FREE_MAIL


def clean_company(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip())
    n = COMPANY_SUFFIXES.sub("", n)
    return n


def company_key(name: str) -> str:
    """Lowercase alphanumeric key for matching company names."""
    return re.sub(r"[^a-z0-9]", "", clean_company(name).lower())


def clean_state(value: str) -> str:
    v = (value or "").strip()
    if len(v) == 2:
        return v.upper()
    return US_STATES.get(v.lower(), v)


def seniority(title: str) -> str:
    t = (title or "").lower()
    for level, pattern in SENIORITY_RULES:
        if re.search(pattern, t):
            return level
    return "ic"


def title_case_name(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return v
    if v.isupper() or v.islower():
        return " ".join(p.capitalize() for p in v.split())
    return v
