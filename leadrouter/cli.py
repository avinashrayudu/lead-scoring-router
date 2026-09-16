from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="leadrouter", description="Enrich, dedupe, score and route a lead file.")
    ap.add_argument("input", type=Path, help="CSV of raw leads")
    ap.add_argument("--scoring", type=Path, default=Path("config/scoring.yaml"))
    ap.add_argument("--routing", type=Path, default=Path("config/routing.yaml"))
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--cache", type=Path, default=Path(".cache/enrichment.json"),
                    help="where to keep the per-domain enrichment cache")
    ap.add_argument("--no-cache", action="store_true", help="always call providers")
    args = ap.parse_args(argv)

    cache = None if args.no_cache else args.cache
    report = run(args.input, args.scoring, args.routing, args.out, cache)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
