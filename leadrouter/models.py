from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Lead:
    """One person at one company, as it moves through the pipeline."""

    lead_id: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    company: str = ""
    domain: str = ""
    source: str = ""
    # firmographics (usually filled by enrichment)
    industry: str = ""
    employees: int | None = None
    hq_state: str = ""
    hq_country: str = ""
    tech_stack: list[str] = field(default_factory=list)
    # behavioral signals
    signals: list[str] = field(default_factory=list)
    # pipeline outputs
    seniority: str = ""
    fit_score: int = 0
    intent_score: int = 0
    total_score: int = 0
    tier: str = ""
    owner: str = ""
    route_reason: str = ""
    score_reasons: list[str] = field(default_factory=list)
    enriched_by: list[str] = field(default_factory=list)
    enrichment_cost: float = 0.0
    duplicate_of: str = ""

    def missing(self, fields: list[str]) -> list[str]:
        out = []
        for f in fields:
            v = getattr(self, f)
            if v in ("", None, []):
                out.append(f)
        return out

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        for k in ("tech_stack", "signals", "score_reasons", "enriched_by"):
            row[k] = "; ".join(row[k])
        row["enrichment_cost"] = round(row["enrichment_cost"], 4)
        return row
