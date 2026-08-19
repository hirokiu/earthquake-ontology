"""Command-line conversion entry points."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .model import DatasetSnapshot
from .parsers import (
    FdsnQuakeMlParser, FdsnStationXmlParser, JmaDailyHypocenterParser,
    JmaIntensityParser, JshisFlatFileParser,
)
from .rdf_builder import RdfBuilder


def _write_graph(graph, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"output already exists: {destination}; pass --force to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        graph.serialize(destination=temporary, format="turtle")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def convert_jma_intensity(args: argparse.Namespace) -> int:
    if args.snapshot_output:
        required = (args.snapshot_uri, args.dataset_uri, args.graph_uri)
        if not all(required):
            print("--snapshot-uri, --dataset-uri, and --graph-uri are required with --snapshot-output", file=sys.stderr)
            return 2
    outputs = [args.output] + ([args.snapshot_output] if args.snapshot_output else [])
    existing = [path for path in outputs if path.exists()]
    if existing and not args.force:
        print(f"output already exists: {existing[0]}; pass --force to replace it", file=sys.stderr)
        return 2

    source_bytes = args.input.read_bytes()
    try:
        source_text = source_bytes.decode(args.encoding)
    except UnicodeDecodeError as exc:
        print(f"failed to decode {args.input} as {args.encoding}: {exc}", file=sys.stderr)
        return 2

    parsed = JmaIntensityParser(args.source_uri).parse_lines(source_text.splitlines())
    if parsed.issues:
        for issue in parsed.issues:
            print(json.dumps(asdict(issue), ensure_ascii=False), file=sys.stderr)
        if not args.allow_issues:
            print("conversion aborted because invalid records were found", file=sys.stderr)
            return 2

    builder = RdfBuilder()
    _write_graph(builder.build_dataset(parsed), args.output, args.force)

    if args.snapshot_output:
        snapshot = DatasetSnapshot(
            uri=args.snapshot_uri,
            dataset_uri=args.dataset_uri,
            source_uri=args.source_uri,
            generated_at=datetime.now(timezone.utc),
            source_sha256=hashlib.sha256(source_bytes).hexdigest(),
            graph_uri=args.graph_uri,
            previous_snapshot_uri=args.previous_snapshot_uri,
            converter_version=__version__,
        )
        metadata = builder.new_graph()
        builder.add_snapshot(metadata, snapshot)
        _write_graph(metadata, args.snapshot_output, args.force)
    return 0


def _convert_parsed(parsed, output: Path, force: bool, allow_issues: bool) -> int:
    if parsed.issues:
        for issue in parsed.issues:
            print(json.dumps(asdict(issue), ensure_ascii=False), file=sys.stderr)
        if not allow_issues:
            print("conversion aborted because invalid records were found", file=sys.stderr)
            return 2
    _write_graph(RdfBuilder().build_dataset(parsed), output, force)
    return 0


def convert_jma_daily(args: argparse.Namespace) -> int:
    html = args.input.read_text(encoding=args.encoding)
    parsed = JmaDailyHypocenterParser(args.source_uri).parse_html(html)
    return _convert_parsed(parsed, args.output, args.force, args.allow_issues)


def convert_jshis_flatfile(args: argparse.Namespace) -> int:
    parsed = JshisFlatFileParser(args.source_uri).parse_zip(args.input)
    return _convert_parsed(parsed, args.output, args.force, args.allow_issues)


def convert_fdsn_events(args: argparse.Namespace) -> int:
    parsed = FdsnQuakeMlParser(args.source_uri).parse_file(args.input)
    return _convert_parsed(parsed, args.output, args.force, args.allow_issues)


def convert_fdsn_stations(args: argparse.Namespace) -> int:
    parsed = FdsnStationXmlParser(args.source_uri).parse_file(args.input)
    return _convert_parsed(parsed, args.output, args.force, args.allow_issues)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert earthquake provider data to RDF")
    subparsers = parser.add_subparsers(dest="command", required=True)
    jma = subparsers.add_parser("jma-intensity", help="convert a JMA monthly fixed-width intensity file")
    jma.add_argument("input", type=Path)
    jma.add_argument("output", type=Path)
    jma.add_argument("--source-uri", required=True, help="authoritative provider file or API URI")
    jma.add_argument("--encoding", default="shift_jis")
    jma.add_argument("--allow-issues", action="store_true", help="write valid records even if other records fail")
    jma.add_argument("--force", action="store_true", help="replace existing local output files")
    jma.add_argument("--snapshot-output", type=Path)
    jma.add_argument("--snapshot-uri")
    jma.add_argument("--dataset-uri")
    jma.add_argument("--graph-uri")
    jma.add_argument("--previous-snapshot-uri")
    jma.set_defaults(handler=convert_jma_intensity)
    daily = subparsers.add_parser("jma-daily", help="convert a JMA provisional daily hypocenter HTML page")
    daily.add_argument("input", type=Path)
    daily.add_argument("output", type=Path)
    daily.add_argument("--source-uri", required=True)
    daily.add_argument("--encoding", default="utf-8")
    daily.add_argument("--allow-issues", action="store_true")
    daily.add_argument("--force", action="store_true")
    daily.set_defaults(handler=convert_jma_daily)
    flat = subparsers.add_parser("jshis-flatfile", help="convert a J-SHIS ground-motion flat-file ZIP")
    flat.add_argument("input", type=Path)
    flat.add_argument("output", type=Path)
    flat.add_argument("--source-uri", required=True)
    flat.add_argument("--allow-issues", action="store_true")
    flat.add_argument("--force", action="store_true")
    flat.set_defaults(handler=convert_jshis_flatfile)
    events = subparsers.add_parser("fdsn-events", help="convert an FDSN QuakeML event response")
    events.add_argument("input", type=Path)
    events.add_argument("output", type=Path)
    events.add_argument("--source-uri", required=True)
    events.add_argument("--allow-issues", action="store_true")
    events.add_argument("--force", action="store_true")
    events.set_defaults(handler=convert_fdsn_events)
    stations = subparsers.add_parser("fdsn-stations", help="convert FDSN StationXML")
    stations.add_argument("input", type=Path)
    stations.add_argument("output", type=Path)
    stations.add_argument("--source-uri", required=True)
    stations.add_argument("--allow-issues", action="store_true")
    stations.add_argument("--force", action="store_true")
    stations.set_defaults(handler=convert_fdsn_stations)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (FileExistsError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
