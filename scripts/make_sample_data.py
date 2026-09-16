"""Generate a reproducible fake lead file plus the enrichment snapshots.

All companies and people are invented.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

random.seed(7)
ROOT = Path(__file__).resolve().parents[1] / "data"

PREFIX = ["Harbor", "Peak", "Golden", "Wild", "True", "Bright", "Little", "North", "Honest",
          "Blue", "Maple", "Sunny", "Rustic", "Urban", "Coastal", "Evergreen", "Kind", "Salt"]
SUFFIX = ["Brew", "Pantry", "Botanicals", "Snacks", "Paws", "Kitchen", "Creamery", "Goods",
          "Roasters", "Skin", "Harvest", "Bakery", "Provisions", "Sips", "Grain"]
INDUSTRY_BY_SUFFIX = {
    "Brew": "Food & Beverage", "Pantry": "Food & Beverage", "Botanicals": "Personal Care",
    "Snacks": "Food & Beverage", "Paws": "Pet Products", "Kitchen": "Food & Beverage",
    "Creamery": "Food & Beverage", "Goods": "Consumer Goods", "Roasters": "Food & Beverage",
    "Skin": "Personal Care", "Harvest": "Food & Beverage", "Bakery": "Food & Beverage",
    "Provisions": "Retail", "Sips": "Food & Beverage", "Grain": "Consumer Goods",
}
STATES = ["NY", "NJ", "CA", "TX", "CO", "IL", "MA", "WA", "FL", "GA", "OR", "PA"]
FIRST = ["Alex", "Jamie", "Taylor", "Morgan", "Riley", "Casey", "Drew", "Avery", "Quinn",
         "Rowan", "Sasha", "Kai", "Elena", "Marcus", "Nina", "Omar", "Grace", "Theo"]
LAST = ["Park", "Rivera", "Singh", "Walsh", "Kim", "Moreno", "Foster", "Ibrahim", "Cole",
        "Nguyen", "Bauer", "Lopez", "Shah", "Reed", "Duarte", "Hale", "Ito", "Brooks"]
TITLES = ["Founder & CEO", "VP of Sales", "Head of Growth", "Director of Operations",
          "Ecommerce Manager", "Sales Operations Manager", "Marketing Coordinator",
          "Chief Revenue Officer", "Brand Manager", "Operations Associate", "Co-Founder",
          "Director, Retail Sales", "Account Executive", "Senior Revenue Analyst"]
SIGNALS = ["demo_request", "pricing_page_visit", "webinar_attended", "new_retail_launch",
           "hiring_sales_ops", "funding_last_90d", "content_download", "newsletter_signup"]
SOURCES = ["website", "webinar", "event", "outbound", "partner"]
STACK = ["Shopify", "Faire", "Amazon Seller Central", "HubSpot", "Salesforce", "Klaviyo", "NetSuite"]

companies = []
seen = set()
while len(companies) < 60:
    name = f"{random.choice(PREFIX)} {random.choice(SUFFIX)}"
    if name in seen:
        continue
    seen.add(name)
    domain = name.lower().replace(" ", "") + ".com"
    industry = INDUSTRY_BY_SUFFIX[name.split()[1]]
    employees = random.choice([4, 8, 15, 28, 45, 70, 120, 260, 480, 900, 2200])
    country = "US" if random.random() > 0.08 else random.choice(["CA", "GB", "DE"])
    companies.append({
        "company": name, "domain": domain, "industry": industry, "employees": employees,
        "hq_state": random.choice(STATES) if country == "US" else "",
        "hq_country": country,
        "tech_stack": "|".join(random.sample(STACK, k=random.randint(1, 3))),
    })
companies[0].update(company="Harbor Brew", domain="harborbrew.com", industry="Food & Beverage")
companies[1].update(company="Peak Pantry", domain="peakpantry.com", industry="Food & Beverage")

ROOT.mkdir(parents=True, exist_ok=True)

# The CRM knows about a third of the accounts, the vendors know most of the rest.
crm = companies[:20]
firmo = [c for c in companies[10:] if random.random() > 0.1]
tech = [c for c in companies if random.random() > 0.3]

def dump(path, rows, fields):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})

dump(ROOT / "crm_accounts.csv", crm, ["domain", "company", "industry", "employees", "hq_state", "hq_country", "tech_stack"])
dump(ROOT / "vendor_firmographics.csv", firmo, ["domain", "industry", "employees", "hq_state", "hq_country"])
dump(ROOT / "vendor_technographics.csv", tech, ["domain", "tech_stack"])

rows = []
for i in range(1, 181):
    c = random.choice(companies)
    fn, ln = random.choice(FIRST), random.choice(LAST)
    email = f"{fn.lower()}.{ln.lower()}@{c['domain']}"
    website = random.choice([c["domain"], "https://www." + c["domain"], "www." + c["domain"] + "/about", ""])
    if random.random() < 0.07:
        email = f"{fn.lower()}{ln.lower()}{random.randint(1, 99)}@gmail.com"
        website = ""
    rows.append({
        "lead_id": f"L{i:05d}",
        "email": email.upper() if random.random() < 0.05 else email,
        "first_name": fn.upper() if random.random() < 0.05 else fn,
        "last_name": ln,
        "title": random.choice(TITLES),
        "company": c["company"] + random.choice(["", "", " Inc.", " LLC", ", Co."]),
        "website": website,
        "source": random.choice(SOURCES),
        "signals": "|".join(random.sample(SIGNALS, k=random.choice([0, 0, 1, 1, 2, 3]))),
    })

# Plant a few duplicates the way they show up in real imports.
for src in random.sample(rows, 8):
    dup = dict(src)
    dup["lead_id"] = f"L{len(rows) + 1:05d}"
    dup["email"] = src["email"].upper() if random.random() < 0.5 else src["email"]
    dup["source"] = "event"
    rows.append(dup)

with open(ROOT / "sample_leads.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"wrote {len(rows)} leads and {len(companies)} companies to {ROOT}")
