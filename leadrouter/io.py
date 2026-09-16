from __future__ import annotations

import csv
from pathlib import Path

from .models import Lead
from .normalize import (
    clean_company,
    clean_domain,
    clean_state,
    domain_from_email,
    is_free_mail,
    seniority,
    title_case_name,
)


def _split(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split("|") if v.strip()]


def read_leads(path: Path) -> list[Lead]:
    leads = []
    with open(path, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=1):
            email = (row.get("email") or "").strip().lower()
            domain = clean_domain(row.get("website") or row.get("domain") or "")
            if not domain:
                d = domain_from_email(email)
                domain = "" if is_free_mail(d) else d
            employees = (row.get("employees") or "").strip()
            lead = Lead(
                lead_id=row.get("lead_id") or f"L{i:05d}",
                email=email,
                first_name=title_case_name(row.get("first_name", "")),
                last_name=title_case_name(row.get("last_name", "")),
                title=(row.get("title") or "").strip(),
                company=clean_company(row.get("company", "")),
                domain=domain,
                source=(row.get("source") or "").strip().lower(),
                industry=(row.get("industry") or "").strip(),
                employees=int(float(employees)) if employees else None,
                hq_state=clean_state(row.get("state", "")),
                hq_country=(row.get("country") or "").strip().upper(),
                signals=_split(row.get("signals", "")),
            )
            lead.seniority = seniority(lead.title)
            leads.append(lead)
    return leads


def write_leads(leads: list[Lead], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [l.to_row() for l in leads]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def hubspot_payload(lead: Lead) -> dict:
    """Shape a routed lead as a HubSpot contact upsert body."""
    return {
        "idProperty": "email",
        "id": lead.email,
        "properties": {
            "email": lead.email,
            "firstname": lead.first_name,
            "lastname": lead.last_name,
            "jobtitle": lead.title,
            "company": lead.company,
            "website": lead.domain,
            "lead_fit_score": lead.fit_score,
            "lead_intent_score": lead.intent_score,
            "lead_tier": lead.tier,
            "lead_route_reason": lead.route_reason,
            "hubspot_owner_name": lead.owner,
        },
    }
