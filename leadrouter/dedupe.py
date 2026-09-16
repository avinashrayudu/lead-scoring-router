"""Duplicate detection.

Two leads are the same person when the email matches, or when the domain and
full name match (people change email formats but rarely their name and
employer at the same time). The earliest record wins; the rest point to it.
"""
from __future__ import annotations

from .models import Lead


def _person_key(lead: Lead) -> str:
    return f"{lead.domain}|{lead.first_name.lower()}|{lead.last_name.lower()}"


def mark_duplicates(leads: list[Lead]) -> int:
    by_email: dict[str, str] = {}
    by_person: dict[str, str] = {}
    count = 0
    for lead in leads:
        email = lead.email.lower()
        pkey = _person_key(lead)
        original = by_email.get(email) if email else None
        if not original and lead.domain and lead.first_name and lead.last_name:
            original = by_person.get(pkey)
        if original:
            lead.duplicate_of = original
            count += 1
            continue
        if email:
            by_email[email] = lead.lead_id
        if lead.domain and lead.first_name and lead.last_name:
            by_person[pkey] = lead.lead_id
    return count
