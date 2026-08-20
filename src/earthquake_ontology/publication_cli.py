"""CLI for the production publication pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx

from .publication import publish


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch, rebuild, validate, and blue-green publish earthquake RDF")
    parser.add_argument("--config", type=Path, default=Path("config/publication.yaml"))
    parser.add_argument("--force", action="store_true", help="publish even when source checksums did not change")
    parser.add_argument("--dry-run", action="store_true", help="fetch and print commands without changing the RDF store")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return publish(args.config, force=args.force, dry_run=args.dry_run)
    except (OSError, ValueError, RuntimeError, KeyError, httpx.HTTPError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
