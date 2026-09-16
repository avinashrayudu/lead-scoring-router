"""Fit and intent scoring.

Fit answers "should we ever sell to this account?" and comes from
firmographics and the person's role. Intent answers "is now a good time?"
and comes from signals. Keeping them separate matters: a perfect-fit account
with no intent goes to nurture, not to a rep's call list.

Every point awarded writes a reason, so a rep can see why a lead landed
in their queue.
"""
from __future__ import annotations

from .models import Lead
from .normalize import is_free_mail


def _in_band(value: int | None, band: dict) -> bool:
    if value is None:
        return False
    lo = band.get("min", float("-inf"))
    hi = band.get("max", float("inf"))
    return lo <= value <= hi


def score_fit(lead: Lead, cfg: dict) -> int:
    points = 0

    industry_points = cfg.get("industries", {})
    if lead.industry in industry_points:
        p = industry_points[lead.industry]
        points += p
        lead.score_reasons.append(f"industry {lead.industry} +{p}")

    for band in cfg.get("employee_bands", []):
        if _in_band(lead.employees, band):
            points += band["points"]
            lead.score_reasons.append(f"{lead.employees} employees +{band['points']}")
            break

    seniority_points = cfg.get("seniority", {})
    p = seniority_points.get(lead.seniority, 0)
    if p:
        points += p
        lead.score_reasons.append(f"seniority {lead.seniority} +{p}")

    keywords = cfg.get("title_keywords", {})
    title = lead.title.lower()
    for kw, p in keywords.items():
        if kw in title:
            points += p
            lead.score_reasons.append(f"title has '{kw}' +{p}")
            break

    stack_points = cfg.get("tech_stack", {})
    for tool in lead.tech_stack:
        if tool in stack_points:
            p = stack_points[tool]
            points += p
            lead.score_reasons.append(f"uses {tool} +{p}")

    geo = cfg.get("countries", {})
    if lead.hq_country and lead.hq_country not in geo.get("allowed", [lead.hq_country]):
        penalty = geo.get("outside_penalty", -30)
        points += penalty
        lead.score_reasons.append(f"outside target countries {penalty}")

    if cfg.get("free_mail_penalty") and lead.source != "event" and lead.email and "@" in lead.email:
        if is_free_mail(lead.email.split("@")[1]):
            p = cfg["free_mail_penalty"]
            points += p
            lead.score_reasons.append(f"personal email {p}")

    return max(0, min(100, points))


def score_intent(lead: Lead, cfg: dict) -> int:
    weights = cfg.get("signals", {})
    points = 0
    for sig in lead.signals:
        p = weights.get(sig, 0)
        if p:
            points += p
            lead.score_reasons.append(f"signal {sig} +{p}")
    return max(0, min(100, points))


def tier_for(fit: int, intent: int, cfg: dict) -> str:
    t = cfg["tiers"]
    if fit >= t["fit_high"] and intent >= t["intent_high"]:
        return "A"
    if fit >= t["fit_high"]:
        return "B"
    if fit >= t["fit_low"] and intent >= t["intent_high"]:
        return "B"
    if fit >= t["fit_low"]:
        return "C"
    return "D"


def score_all(leads: list[Lead], cfg: dict) -> None:
    w_fit = cfg.get("weights", {}).get("fit", 0.6)
    w_int = cfg.get("weights", {}).get("intent", 0.4)
    for lead in leads:
        if lead.duplicate_of:
            continue
        lead.score_reasons = []
        lead.fit_score = score_fit(lead, cfg["fit"])
        lead.intent_score = score_intent(lead, cfg["intent"])
        lead.total_score = round(lead.fit_score * w_fit + lead.intent_score * w_int)
        lead.tier = tier_for(lead.fit_score, lead.intent_score, cfg)
