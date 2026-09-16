# lead-scoring-router

![tests](https://github.com/avinashrayudu/lead-scoring-router/actions/workflows/tests.yml/badge.svg)

A small, config-driven pipeline that takes a messy lead file and returns every lead cleaned, enriched, scored, and assigned to a rep, with a written reason for each decision.

It does the same job as a Clay table plus CRM assignment rules, but in plain Python, so every step can be tested and diffed.

```
raw CSV ─► normalize ─► dedupe ─► enrich (waterfall + cache) ─► score (fit × intent) ─► route ─► CSV + HubSpot upsert JSON
```

## Why I built it

On most small GTM teams, lead handling lives in three places: an enrichment tool, a spreadsheet of scoring rules somebody wrote once, and CRM assignment rules nobody wants to touch. When a good lead lands with the wrong rep, or sits unassigned, nobody can say why.

This project keeps all of that in two YAML files and makes every decision explainable. Each lead leaves the pipeline with its fit score, intent score, tier, owner, and the reasons behind all four.

## What it does

| Step | What happens | Where |
|---|---|---|
| Normalize | Strips `https://www.` from domains, pulls the domain from the work email, drops `Inc.`/`LLC`, fixes all-caps names, maps state names to codes, and reads seniority from the title | `leadrouter/normalize.py` |
| Dedupe | Marks a lead as a duplicate when the email matches, or when the same first and last name show up at the same domain. The first record wins | `leadrouter/dedupe.py` |
| Enrich | Tries providers cheapest first. It skips any provider that can't fill a missing field and stops when the required fields are full. Results are cached per domain, and a provider that came back empty isn't asked again | `leadrouter/enrich.py` |
| Score | Fit comes from industry, size, seniority, title, stack and country. Intent comes from signals. Tier comes from both, and every point is logged | `leadrouter/score.py` |
| Route | Existing accounts go to their current owner first. After that, the first matching rule wins, and reps are picked round-robin within their capacity. Tier D goes to a disqualified queue, tier C to nurture | `leadrouter/route.py` |
| Output | `routed_leads.csv`, `hubspot_upsert.json` (a contacts batch-upsert body keyed on email) and `run_report.json` | `leadrouter/io.py` |

## Run it

```bash
pip install -e ".[dev]"
python scripts/make_sample_data.py      # 188 fake leads, 60 fake companies
python -m leadrouter data/sample_leads.csv --out out
pytest -q
```

Sample run:

```json
{
  "leads_in": 188,
  "duplicates": 10,
  "enrichment": {
    "calls": {"internal_crm": 58, "tech_vendor": 40, "firmo_vendor": 41},
    "cache_hits": 105,
    "spend": 2.44,
    "incomplete_after_waterfall": 37
  },
  "tiers": {"A": 33, "B": 83, "C": 24, "D": 38},
  "owners": {"Jordan Blake": 30, "Luis Ortega": 25, "Maya Chen": 25, "Priya Nair": 14,
             "Sam Okafor": 14, "marketing_nurture": 24, "nurture_disqualified": 38, "unassigned": 8}
}
```

Run it a second time and the spend goes to `0.0`, because every domain is already in the cache.

One routed lead, as a rep would see it:

| lead | fit | intent | tier | owner | why |
|---|---|---|---|---|---|
| Co-Founder, Salt Brew | 74 | 65 | A | Jordan Blake | industry Food & Beverage +30; 28 employees +20; seniority c_level +20; uses Salesforce +4; signal new_retail_launch +20; signal demo_request +45 |

## Things the sample run surfaces on purpose

- **8 leads end up unassigned.** They matched the east mid-market rule, but both reps in that pool were already at capacity. In a real CRM that failure is silent. Here it shows up in the report, with the reason on the row. The fix is a business call, either a spillover pool or higher capacity, not a code change.
- **37 leads are still incomplete after the waterfall.** No provider knew those domains. The spend report shows whether adding a third vendor is worth it.
- **Account owners bypass capacity.** An existing customer always goes back to the person who owns the relationship, even when that rep is full.

## Configuration

`config/scoring.yaml` holds the ICP. The example ICP is a retail analytics product sold to emerging consumer brands. Every weight is a number you can change to see what happens:

```yaml
fit:
  industries: {Food & Beverage: 30, Consumer Goods: 25, Personal Care: 20}
  employee_bands:
    - {min: 11, max: 50, points: 20}
    - {min: 51, max: 500, points: 25}
intent:
  signals: {demo_request: 45, pricing_page_visit: 25, new_retail_launch: 20}
tiers: {fit_high: 60, fit_low: 35, intent_high: 30}
```

`config/routing.yaml` holds the reps, their capacity, the named accounts, and the ordered rules.

To use a real enrichment vendor, add an `http` provider. It reads its key from an environment variable and maps response keys onto lead fields. See the commented block at the bottom of `scoring.yaml`.

## Design choices

- **Fit and intent stay separate.** A perfect-fit account with no intent belongs in nurture, not on a rep's call list, and one blended number hides that.
- **Cheapest provider first, and only when it can help.** Paying a vendor for fields the lead already has is the easiest spend to cut.
- **Explanations are part of the output.** Reps trust routing they can read.
- **Rules are data.** Changing territories shouldn't need a deploy.

## Layout

```
config/            scoring and routing rules
data/              fake leads + enrichment snapshots (generated)
leadrouter/        the pipeline
scripts/           sample data generator
tests/             unit + end-to-end tests
```

All company and person names in `data/` are made up.
