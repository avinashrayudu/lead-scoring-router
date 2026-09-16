import csv
import json
from pathlib import Path

from leadrouter.dedupe import mark_duplicates
from leadrouter.enrich import DomainCache, enrich
from leadrouter.models import Lead
from leadrouter.pipeline import run
from leadrouter.route import Router
from leadrouter.score import score_all, tier_for

ROOT = Path(__file__).resolve().parents[1]

SCORING = {
    "weights": {"fit": 0.6, "intent": 0.4},
    "tiers": {"fit_high": 60, "fit_low": 35, "intent_high": 30},
    "fit": {
        "industries": {"Food & Beverage": 30},
        "employee_bands": [{"min": 11, "max": 500, "points": 25}],
        "seniority": {"vp": 18},
        "title_keywords": {"sales": 10},
        "countries": {"allowed": ["US"], "outside_penalty": -30},
    },
    "intent": {"signals": {"demo_request": 45}},
}


class FakeProvider:
    def __init__(self, name, cost, fields, data):
        self.name, self.cost_per_call, self.fields, self.data = name, cost, fields, data
        self.calls = 0

    def lookup(self, lead):
        self.calls += 1
        return self.data.get(lead.domain, {})


def make_lead(**kw):
    base = dict(lead_id="L1", email="a@x.com", first_name="A", last_name="B", domain="x.com")
    base.update(kw)
    return Lead(**base)


def test_waterfall_stops_when_complete_and_uses_cheapest_first():
    cheap = FakeProvider("cheap", 0.0, ("industry", "employees"), {"x.com": {"industry": "Food & Beverage", "employees": 40}})
    pricey = FakeProvider("pricey", 0.05, ("industry", "employees"), {"x.com": {"industry": "Retail", "employees": 999}})
    lead = make_lead()
    stats = enrich([lead], [pricey, cheap], ["industry", "employees"])
    assert lead.industry == "Food & Beverage"
    assert pricey.calls == 0
    assert stats.spend == 0


def test_waterfall_falls_through_and_tracks_spend():
    cheap = FakeProvider("cheap", 0.0, ("industry", "employees"), {"x.com": {"industry": "Food & Beverage"}})
    pricey = FakeProvider("pricey", 0.05, ("employees",), {"x.com": {"employees": 40}})
    lead = make_lead()
    stats = enrich([lead], [cheap, pricey], ["industry", "employees"])
    assert (lead.industry, lead.employees) == ("Food & Beverage", 40)
    assert stats.spend == 0.05
    assert lead.enriched_by == ["cheap", "pricey"]


def test_cache_skips_providers_already_tried(tmp_path):
    empty = FakeProvider("empty", 0.05, ("industry",), {})
    cache = DomainCache(tmp_path / "c.json")
    enrich([make_lead()], [empty], ["industry"], cache)
    cache.save()
    enrich([make_lead()], [empty], ["industry"], DomainCache(tmp_path / "c.json"))
    assert empty.calls == 1


def test_duplicates_by_email_and_by_name_at_domain():
    leads = [
        make_lead(lead_id="1", email="sam@x.com", first_name="Sam", last_name="Lee"),
        make_lead(lead_id="2", email="SAM@x.com", first_name="Sam", last_name="Lee"),
        make_lead(lead_id="3", email="slee@x.com", first_name="Sam", last_name="Lee"),
        make_lead(lead_id="4", email="kim@x.com", first_name="Kim", last_name="Ho"),
    ]
    assert mark_duplicates(leads) == 2
    assert [l.duplicate_of for l in leads] == ["", "1", "1", ""]


def test_scoring_explains_every_point():
    lead = make_lead(industry="Food & Beverage", employees=40, title="VP Sales",
                     seniority="vp", hq_country="US", signals=["demo_request"])
    score_all([lead], SCORING)
    assert lead.fit_score == 30 + 25 + 18 + 10
    assert lead.intent_score == 45
    assert lead.tier == "A"
    assert len(lead.score_reasons) == 5


def test_outside_country_penalty():
    lead = make_lead(industry="Food & Beverage", employees=40, hq_country="DE")
    score_all([lead], SCORING)
    assert lead.fit_score == 25
    assert lead.tier == "D"


def test_tiers():
    t = SCORING
    assert tier_for(70, 40, t) == "A"
    assert tier_for(70, 0, t) == "B"
    assert tier_for(40, 40, t) == "B"
    assert tier_for(40, 0, t) == "C"
    assert tier_for(10, 90, t) == "D"


def test_router_round_robin_capacity_and_owner_override():
    router = Router.from_config({
        "reps": [{"name": "A", "capacity": 1}, {"name": "B", "capacity": 1}],
        "account_owners": {"owned.com": "B"},
        "rules": [{"name": "all", "when": {"tier_in": ["A"]}, "pool": ["A", "B"]}],
    })
    leads = [make_lead(lead_id=str(i), domain=f"d{i}.com", tier="A", total_score=10 - i) for i in range(3)]
    leads.append(make_lead(lead_id="own", domain="owned.com", tier="A", total_score=1))
    router.assign_all(leads)
    assert [l.owner for l in leads[:3]] == ["A", "B", "unassigned"]
    assert "capacity" in leads[2].route_reason
    assert leads[3].owner == "B"


def test_end_to_end_sample(tmp_path):
    report = run(ROOT / "data/sample_leads.csv", ROOT / "config/scoring.yaml",
                 ROOT / "config/routing.yaml", tmp_path, None)
    assert report["leads_in"] == 188
    assert report["duplicates"] >= 8
    with open(tmp_path / "routed_leads.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert all(r["owner"] or r["duplicate_of"] for r in rows)
    payload = json.loads((tmp_path / "hubspot_upsert.json").read_text())
    assert payload["inputs"][0]["idProperty"] == "email"
