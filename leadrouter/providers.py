"""Enrichment providers.

Every provider answers one question: given a lead, what fields can you fill?
Real vendors (Apollo, Clearbit, People Data Labs, a Clay table) all fit this
shape. The CSV provider lets the whole pipeline run offline against a local
snapshot, which is also how the tests work.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import Lead
from .normalize import clean_domain


class Provider(Protocol):
    name: str
    cost_per_call: float
    fields: tuple[str, ...]

    def lookup(self, lead: Lead) -> dict: ...


@dataclass
class CsvProvider:
    """Looks up firmographics by domain from a local CSV snapshot."""

    name: str
    path: Path
    cost_per_call: float = 0.0
    fields: tuple[str, ...] = ("industry", "employees", "hq_state", "hq_country", "tech_stack")

    def __post_init__(self) -> None:
        self._rows: dict[str, dict] = {}
        with open(self.path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self._rows[clean_domain(row["domain"])] = row

    def lookup(self, lead: Lead) -> dict:
        row = self._rows.get(clean_domain(lead.domain))
        if not row:
            return {}
        out: dict = {}
        for f in self.fields:
            value = (row.get(f) or "").strip()
            if not value:
                continue
            if f == "employees":
                try:
                    out[f] = int(float(value))
                except ValueError:
                    continue
            elif f in ("tech_stack", "signals"):
                out[f] = [v.strip() for v in value.split("|") if v.strip()]
            else:
                out[f] = value
        return out


@dataclass
class HttpJsonProvider:
    """Template for a real vendor API.

    Calls ``{base_url}?domain=<domain>`` with a bearer token read from the
    environment and maps response keys onto lead fields with ``field_map``.
    Not used by the sample run; wire it up in config when you have a key.
    """

    name: str
    base_url: str
    token_env: str
    field_map: dict[str, str]
    cost_per_call: float = 0.01
    timeout: float = 10.0

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(self.field_map.values())

    def lookup(self, lead: Lead) -> dict:
        token = os.environ.get(self.token_env)
        if not token or not lead.domain:
            return {}
        req = urllib.request.Request(
            f"{self.base_url}?domain={clean_domain(lead.domain)}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.load(resp)
        except Exception:
            return {}
        return {dst: payload[src] for src, dst in self.field_map.items() if payload.get(src)}


def build_providers(cfg: list[dict], base_dir: Path) -> list:
    providers = []
    for p in cfg:
        kind = p.get("type", "csv")
        if kind == "csv":
            providers.append(
                CsvProvider(
                    name=p["name"],
                    path=(base_dir / p["path"]).resolve(),
                    cost_per_call=float(p.get("cost_per_call", 0)),
                    fields=tuple(p.get("fields", CsvProvider.fields)),
                )
            )
        elif kind == "http":
            providers.append(
                HttpJsonProvider(
                    name=p["name"],
                    base_url=p["base_url"],
                    token_env=p["token_env"],
                    field_map=p["field_map"],
                    cost_per_call=float(p.get("cost_per_call", 0.01)),
                )
            )
        else:
            raise ValueError(f"unknown provider type: {kind}")
    return providers
