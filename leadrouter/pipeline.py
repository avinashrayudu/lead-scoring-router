from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml

from .dedupe import mark_duplicates
from .enrich import DomainCache, enrich
from .io import hubspot_payload, read_leads, write_leads
from .providers import build_providers
from .route import Router
from .score import score_all


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def run(input_csv: Path, scoring_cfg: Path, routing_cfg: Path, out_dir: Path,
        cache_path: Path | None = None) -> dict:
    scoring = load_yaml(scoring_cfg)
    routing = load_yaml(routing_cfg)

    leads = read_leads(input_csv)
    dupes = mark_duplicates(leads)

    providers = build_providers(scoring.get("enrichment", {}).get("providers", []),
                                Path(scoring_cfg).parent)
    required = scoring.get("enrichment", {}).get("required_fields", [])
    cache = DomainCache(cache_path) if cache_path else None
    stats = enrich(leads, providers, required, cache)
    if cache:
        cache.save()

    score_all(leads, scoring)
    router = Router.from_config(routing)
    router.assign_all(leads)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_leads(leads, out_dir / "routed_leads.csv")
    payloads = [hubspot_payload(l) for l in leads if not l.duplicate_of and l.email]
    (out_dir / "hubspot_upsert.json").write_text(json.dumps({"inputs": payloads}, indent=2))

    live = [l for l in leads if not l.duplicate_of]
    report = {
        "leads_in": len(leads),
        "duplicates": dupes,
        "enrichment": stats.summary(),
        "tiers": dict(sorted(Counter(l.tier for l in live).items())),
        "owners": dict(sorted(Counter(l.owner for l in live).items())),
        "rep_load": {r.name: f"{r.assigned}/{r.capacity}" for r in router.reps.values()},
    }
    (out_dir / "run_report.json").write_text(json.dumps(report, indent=2))
    return report
