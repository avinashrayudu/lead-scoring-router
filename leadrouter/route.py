"""Routing.

Rules are checked top to bottom and the first match wins, the same way most
CRM assignment rules work. Inside a matching rule, leads go round-robin to
the rep with the fewest assignments who still has capacity. Existing
accounts always go back to their current owner.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Lead


@dataclass
class Rep:
    name: str
    capacity: int
    assigned: int = 0

    @property
    def full(self) -> bool:
        return self.assigned >= self.capacity


@dataclass
class Router:
    rules: list[dict]
    reps: dict[str, Rep]
    account_owners: dict[str, str] = field(default_factory=dict)
    fallback_queue: str = "unassigned"

    @classmethod
    def from_config(cls, cfg: dict) -> "Router":
        reps = {r["name"]: Rep(r["name"], int(r.get("capacity", 50))) for r in cfg["reps"]}
        return cls(
            rules=cfg["rules"],
            reps=reps,
            account_owners={k.lower(): v for k, v in cfg.get("account_owners", {}).items()},
            fallback_queue=cfg.get("fallback_queue", "unassigned"),
        )

    @staticmethod
    def _matches(lead: Lead, when: dict) -> bool:
        for key, expected in when.items():
            if key == "tier_in":
                if lead.tier not in expected:
                    return False
            elif key == "state_in":
                if lead.hq_state not in expected:
                    return False
            elif key == "min_employees":
                if (lead.employees or 0) < expected:
                    return False
            elif key == "max_employees":
                if lead.employees is None or lead.employees > expected:
                    return False
            elif key == "source_in":
                if lead.source not in expected:
                    return False
            else:
                raise ValueError(f"unknown routing condition: {key}")
        return True

    def _pick(self, pool: list[str]) -> Rep | None:
        open_reps = [self.reps[n] for n in pool if not self.reps[n].full]
        if not open_reps:
            return None
        return min(open_reps, key=lambda r: (r.assigned, pool.index(r.name)))

    def assign(self, lead: Lead) -> None:
        owner = self.account_owners.get(lead.domain)
        if owner:
            lead.owner = owner
            lead.route_reason = "existing account owner"
            if owner in self.reps:
                self.reps[owner].assigned += 1
            return

        for rule in self.rules:
            if not self._matches(lead, rule.get("when", {})):
                continue
            if rule.get("queue"):
                lead.owner = rule["queue"]
                lead.route_reason = f"rule '{rule['name']}'"
                return
            rep = self._pick(rule["pool"])
            if rep:
                rep.assigned += 1
                lead.owner = rep.name
                lead.route_reason = f"rule '{rule['name']}', round robin"
                return
            lead.owner = self.fallback_queue
            lead.route_reason = f"rule '{rule['name']}' matched but every rep is at capacity"
            return

        lead.owner = self.fallback_queue
        lead.route_reason = "no rule matched"

    def assign_all(self, leads: list[Lead]) -> None:
        # Best leads first so capacity goes to them.
        for lead in sorted(leads, key=lambda l: -l.total_score):
            if lead.duplicate_of:
                lead.owner = ""
                lead.route_reason = f"duplicate of {lead.duplicate_of}"
                continue
            self.assign(lead)
