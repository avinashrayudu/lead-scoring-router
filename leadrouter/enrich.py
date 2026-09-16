"""Waterfall enrichment.

Providers are tried cheapest-first. A provider is only called if it can fill
at least one field that is still missing, and the waterfall stops as soon as
every required field is present. Results are cached by domain, so a re-run
doesn't pay twice and a provider that already came back empty for a domain
is not asked again.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import Lead


@dataclass
class EnrichmentStats:
    calls: dict[str, int] = field(default_factory=dict)
    cache_hits: int = 0
    spend: float = 0.0
    incomplete: int = 0

    def summary(self) -> dict:
        return {
            "calls": dict(self.calls),
            "cache_hits": self.cache_hits,
            "spend": round(self.spend, 4),
            "incomplete_after_waterfall": self.incomplete,
        }


class DomainCache:
    def __init__(self, path: Path | None):
        self.path = path
        self.data: dict[str, dict] = {}
        if path and path.exists():
            self.data = json.loads(path.read_text())

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def put(self, key: str, value: dict) -> None:
        self.data[key] = value

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True))


def _apply(lead: Lead, found: dict) -> list[str]:
    filled = []
    for key, value in found.items():
        if getattr(lead, key) in ("", None, []) and value not in ("", None, []):
            setattr(lead, key, value)
            filled.append(key)
    return filled


def enrich(
    leads: list[Lead],
    providers: list,
    required: list[str],
    cache: DomainCache | None = None,
) -> EnrichmentStats:
    stats = EnrichmentStats()
    ordered = sorted(providers, key=lambda p: p.cost_per_call)

    for lead in leads:
        if lead.duplicate_of or not lead.domain:
            continue

        entry = cache.get(lead.domain) if cache else None
        if entry:
            stats.cache_hits += 1
            if _apply(lead, entry["fields"]):
                lead.enriched_by.extend(entry["sources"])
        else:
            entry = {"fields": {}, "sources": [], "tried": []}

        for provider in ordered:
            missing = lead.missing(required)
            if not missing:
                break
            if provider.name in entry["tried"]:
                continue  # already asked about this domain, on this run or an earlier one
            if not set(missing) & set(provider.fields):
                continue
            stats.calls[provider.name] = stats.calls.get(provider.name, 0) + 1
            stats.spend += provider.cost_per_call
            lead.enrichment_cost += provider.cost_per_call
            entry["tried"].append(provider.name)
            found = provider.lookup(lead)
            if _apply(lead, found):
                lead.enriched_by.append(provider.name)
                entry["sources"].append(provider.name)
                for k, v in found.items():
                    entry["fields"].setdefault(k, v)

        if lead.missing(required):
            stats.incomplete += 1
        if cache is not None:
            cache.put(lead.domain, entry)

    return stats
