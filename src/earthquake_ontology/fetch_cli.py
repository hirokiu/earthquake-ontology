"""CLI for provider discovery and immutable source acquisition."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import httpx
from pydantic import ValidationError

from .acquisition import DataFetcher
from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover and archive authoritative earthquake data")
    parser.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    parser.add_argument("--source", action="append", dest="sources", help="source ID; repeat to select multiple")
    parser.add_argument("--period", action="append", dest="periods", help="period discovered by the source; repeat as needed")
    parser.add_argument("--force", action="store_true", help="ignore conditional request metadata")
    parser.add_argument("--list", action="store_true", help="discover and print artifacts without downloading")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
        selected = set(args.sources) if args.sources else None
        if selected:
            missing = selected - set(settings.sources)
            if missing:
                raise KeyError(f"unknown source IDs: {', '.join(sorted(missing))}")
        with DataFetcher(settings) as fetcher:
            if args.list:
                for source_id, source in settings.sources.items():
                    if source.enabled and (selected is None or source_id in selected):
                        for artifact in fetcher.discover(source_id, source):
                            if not args.periods or artifact.period in set(args.periods):
                                print(json.dumps(asdict(artifact), ensure_ascii=False))
                return 0
            results = fetcher.fetch_sources(args.sources, set(args.periods) if args.periods else None, force=args.force)
            for result in results:
                print(json.dumps(asdict(result), ensure_ascii=False))
        return 0
    except (ValidationError, httpx.HTTPError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
