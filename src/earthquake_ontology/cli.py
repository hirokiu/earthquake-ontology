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

import httpx
from rdflib import Dataset, URIRef

from . import __version__
from .address_enrichment import GsiAddressEnricher
from .model import DatasetSnapshot
from .parsers import (
    FdsnQuakeMlParser, FdsnStationXmlParser, JmaDailyHypocenterParser, JmaStationCodeParser,
    JmaIntensityParser, JshisFlatFileParser,
)
from .rdf_builder import RdfBuilder
from .parsers.jma_station_details import merge_jma_station_details


OUTPUT_FORMATS = {
    "turtle": ("turtle", "ttl"),
    "ntriples": ("nt", "nt"),
    "nquads": ("nquads", "nq"),
}


def _created_date(value: str | None) -> str:
    if value is None:
        return datetime.now().astimezone().date().isoformat()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("--created-at must use YYYY-MM-DD") from exc


def _output_path(args: argparse.Namespace) -> Path:
    if args.output is not None:
        return args.output
    extension = OUTPUT_FORMATS[args.output_format][1]
    stem = args.input.name
    while Path(stem).suffix.lower() in {".zip", ".xml", ".html", ".dat", ".txt", ".csv", ".tsv"}:
        stem = Path(stem).stem
    prefixes = {
        "fdsn-events": ("usgs-fdsn-events", ("events-", "event-")),
        "fdsn-stations": ("earthscope-fdsn-stations", ("stations-", "station-")),
        "jma-daily": ("jma-daily-hypocenters", ("daily-",)),
        "jma-intensity": ("jma-monthly-intensity", ()),
        "jma-stations": ("jma-intensity-stations", ("code_p", "code-p")),
        "jshis-flatfile": ("jshis-ground-motion-flatfile", ("flatfile-",)),
    }
    prefix, removable = prefixes[args.command]
    for candidate in removable:
        if stem.lower() == candidate.rstrip("-"):
            stem = ""
            break
        if stem.lower().startswith(candidate):
            stem = stem[len(candidate):]
            break
    filename = f"{prefix}{f'-{stem}' if stem else ''}.{extension}"
    return args.output_root / _created_date(args.created_at) / args.command / args.output_format / filename


def _write_graph(
    graph, destination: Path, force: bool, output_format: str = "turtle",
    graph_uri: str | None = None,
) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"output already exists: {destination}; pass --force to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        rdflib_format = OUTPUT_FORMATS[output_format][0]
        serializable = graph
        if output_format == "nquads":
            if not graph_uri:
                raise ValueError("--graph-uri is required for N-Quads output")
            dataset = Dataset()
            named_graph = dataset.graph(URIRef(graph_uri))
            for triple in graph:
                named_graph.add(triple)
            serializable = dataset
        serializable.serialize(destination=temporary, format=rdflib_format, encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _entity_path(output: Path, entity: str) -> Path:
    if entity == "hypocenters" and "-hypocenters" in output.stem:
        return output
    return output.with_name(f"{output.stem}-{entity}{output.suffix}")


def _planned_dataset_paths(parsed, output: Path, split_by_entity: bool) -> list[Path]:
    if not split_by_entity:
        return [output]
    entities = []
    if parsed.hypocenters:
        entities.append("hypocenters")
    if parsed.stations:
        entities.append("stations")
    if parsed.observations or parsed.strong_motion_records:
        entities.append("observed-waves")
    return [_entity_path(output, name) for name in entities]


def _write_dataset(parsed, args: argparse.Namespace, output: Path, graph_uri: str | None = None) -> None:
    builder = RdfBuilder()
    if not args.split_by_entity:
        _write_graph(builder.build_dataset(parsed), output, args.force, args.output_format, graph_uri)
        print(output)
        return
    for entity, graph in builder.iter_entity_graphs(parsed):
        destination = _entity_path(output, entity)
        entity_graph_uri = f"{graph_uri.rstrip('/')}/{entity}" if graph_uri else None
        _write_graph(graph, destination, args.force, args.output_format, entity_graph_uri)
        print(destination)


def convert_jma_intensity(args: argparse.Namespace) -> int:
    args.output = _output_path(args)
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
    _write_dataset(parsed, args, args.output, args.graph_uri)

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


def _convert_parsed(parsed, args: argparse.Namespace) -> int:
    if not _prepare_parsed(parsed, args):
        return 2
    output = _output_path(args)
    _write_dataset(parsed, args, output, args.graph_uri)
    return 0


def _prepare_parsed(parsed, args: argparse.Namespace) -> bool:
    if getattr(args, "clear_address_cache", False) and not getattr(args, "enrich_addresses", False):
        raise ValueError("--clear-address-cache requires --enrich-addresses")
    if getattr(args, "enrich_addresses", False):
        with GsiAddressEnricher(
            args.address_cache, interval_seconds=args.address_request_interval,
        ) as enricher:
            if args.clear_address_cache:
                backup = enricher.clear_cache()
                print(json.dumps({
                    "address_cache_cleared": str(args.address_cache),
                    "backup": str(backup) if backup else None,
                }, ensure_ascii=False), file=sys.stderr)
            parsed.stations, summary = enricher.enrich(parsed.stations)
        print(json.dumps({"address_enrichment": asdict(summary)}, ensure_ascii=False), file=sys.stderr)
    if parsed.issues:
        for issue in parsed.issues:
            print(json.dumps(asdict(issue), ensure_ascii=False), file=sys.stderr)
        if not args.allow_issues:
            print("conversion aborted because invalid records were found", file=sys.stderr)
            return False
    return True


def convert_jma_daily(args: argparse.Namespace) -> int:
    html = args.input.read_text(encoding=args.encoding)
    parsed = JmaDailyHypocenterParser(args.source_uri).parse_html(html)
    return _convert_parsed(parsed, args)


def convert_jshis_flatfile(args: argparse.Namespace) -> int:
    parsed = JshisFlatFileParser(args.source_uri).parse_zip(args.input)
    if not args.split_by_year:
        return _convert_parsed(parsed, args)
    if not _prepare_parsed(parsed, args):
        return 2

    output = _output_path(args)
    by_year = _split_jshis_by_year(parsed)
    year_outputs = {
        year: output.with_name(f"{output.stem}-{year}{output.suffix}")
        for year in by_year
    }
    planned = _planned_dataset_paths(parsed, output, args.split_by_entity)
    for year, dataset in by_year.items():
        planned.extend(_planned_dataset_paths(dataset, year_outputs[year], args.split_by_entity))
    existing = [path for path in planned if path.exists()]
    if existing and not args.force:
        raise FileExistsError(f"output already exists: {existing[0]}; pass --force to replace it")

    _write_dataset(parsed, args, output, args.graph_uri)
    for year, dataset in by_year.items():
        graph_uri = f"{args.graph_uri.rstrip('/')}/{year}" if args.graph_uri else None
        _write_dataset(dataset, args, year_outputs[year], graph_uri)
    return 0


def _split_jshis_by_year(parsed):
    years = sorted({item.origin_time.year for item in parsed.hypocenters})
    result = {}
    for year in years:
        hypocenters = [item for item in parsed.hypocenters if item.origin_time.year == year]
        hypocenter_uris = {item.uri for item in hypocenters}
        observations = [item for item in parsed.observations if item.hypocenter_uri in hypocenter_uris]
        records = [item for item in parsed.strong_motion_records if item.hypocenter_uri in hypocenter_uris]
        station_uris = {item.station_uri for item in observations}
        station_uris.update(item.station_uri for item in records)
        result[year] = type(parsed)(
            hypocenters=hypocenters,
            observations=observations,
            stations=[item for item in parsed.stations if item.uri in station_uris],
            strong_motion_records=records,
        )
    return result


def convert_fdsn_events(args: argparse.Namespace) -> int:
    parsed = FdsnQuakeMlParser(args.source_uri).parse_file(args.input)
    return _convert_parsed(parsed, args)


def convert_fdsn_stations(args: argparse.Namespace) -> int:
    parsed = FdsnStationXmlParser(args.source_uri).parse_file(args.input)
    return _convert_parsed(parsed, args)


def convert_jma_stations(args: argparse.Namespace) -> int:
    parsed = JmaStationCodeParser(args.source_uri).parse_zip(args.input)
    if args.details_html:
        if not args.details_source_uri:
            raise ValueError("--details-source-uri is required with --details-html")
        parsed.stations = merge_jma_station_details(
            parsed.stations, args.details_html, args.details_source_uri,
        )
    return _convert_parsed(parsed, args)


def _add_output_options(parser: argparse.ArgumentParser, include_graph_uri: bool = True) -> None:
    parser.add_argument(
        "--split-by-entity", action="store_true",
        help="write separate hypocenters, stations, and observed-waves files instead of one mixed file",
    )
    parser.add_argument(
        "--output-format", choices=tuple(OUTPUT_FORMATS), default="turtle",
        help="RDF serialization (default: turtle; QLever also accepts ntriples and nquads)",
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("data"),
        help="root used when the positional output is omitted (default: data)",
    )
    parser.add_argument(
        "--created-at", help="creation date for automatic output paths (YYYY-MM-DD; default: local date)",
    )
    if include_graph_uri:
        parser.add_argument("--graph-uri", help="named graph URI; required for nquads")


def _add_address_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--enrich-addresses", action="store_true",
        help="fill missing Japanese station addresses using the GSI reverse geocoder",
    )
    parser.add_argument(
        "--address-cache", type=Path, default=Path("var/cache/gsi-addresses.json"),
        help="persistent GSI result cache",
    )
    parser.add_argument(
        "--address-request-interval", type=float, default=0.2,
        help="minimum delay after uncached GSI requests in seconds",
    )
    parser.add_argument(
        "--clear-address-cache", action="store_true",
        help="back up and clear the complete GSI cache before enrichment",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert earthquake provider data to RDF")
    subparsers = parser.add_subparsers(dest="command", required=True)
    jma = subparsers.add_parser("jma-intensity", help="convert a JMA monthly fixed-width intensity file")
    jma.add_argument("input", type=Path)
    jma.add_argument("output", type=Path, nargs="?")
    jma.add_argument("--source-uri", required=True, help="authoritative provider file or API URI")
    jma.add_argument("--encoding", default="shift_jis")
    jma.add_argument("--allow-issues", action="store_true", help="write valid records even if other records fail")
    jma.add_argument("--force", action="store_true", help="replace existing local output files")
    jma.add_argument("--snapshot-output", type=Path)
    jma.add_argument("--snapshot-uri")
    jma.add_argument("--dataset-uri")
    jma.add_argument("--graph-uri")
    jma.add_argument("--previous-snapshot-uri")
    _add_output_options(jma, include_graph_uri=False)
    jma.set_defaults(handler=convert_jma_intensity)
    daily = subparsers.add_parser("jma-daily", help="convert a JMA provisional daily hypocenter HTML page")
    daily.add_argument("input", type=Path)
    daily.add_argument("output", type=Path, nargs="?")
    daily.add_argument("--source-uri", required=True)
    daily.add_argument("--encoding", default="utf-8")
    daily.add_argument("--allow-issues", action="store_true")
    daily.add_argument("--force", action="store_true")
    _add_output_options(daily)
    daily.set_defaults(handler=convert_jma_daily)
    flat = subparsers.add_parser("jshis-flatfile", help="convert a J-SHIS ground-motion flat-file ZIP")
    flat.add_argument("input", type=Path)
    flat.add_argument("output", type=Path, nargs="?")
    flat.add_argument("--source-uri", required=True)
    flat.add_argument("--allow-issues", action="store_true")
    flat.add_argument("--force", action="store_true")
    flat.add_argument(
        "--split-by-year", action="store_true",
        help="write the complete dataset and additional self-contained files for each event year",
    )
    _add_output_options(flat)
    _add_address_options(flat)
    flat.set_defaults(handler=convert_jshis_flatfile)
    events = subparsers.add_parser("fdsn-events", help="convert an FDSN QuakeML event response")
    events.add_argument("input", type=Path)
    events.add_argument("output", type=Path, nargs="?")
    events.add_argument("--source-uri", required=True)
    events.add_argument("--allow-issues", action="store_true")
    events.add_argument("--force", action="store_true")
    _add_output_options(events)
    events.set_defaults(handler=convert_fdsn_events)
    stations = subparsers.add_parser("fdsn-stations", help="convert FDSN StationXML")
    stations.add_argument("input", type=Path)
    stations.add_argument("output", type=Path, nargs="?")
    stations.add_argument("--source-uri", required=True)
    stations.add_argument("--allow-issues", action="store_true")
    stations.add_argument("--force", action="store_true")
    _add_output_options(stations)
    _add_address_options(stations)
    stations.set_defaults(handler=convert_fdsn_stations)
    jma_stations = subparsers.add_parser("jma-stations", help="convert the JMA intensity-station code ZIP")
    jma_stations.add_argument("input", type=Path)
    jma_stations.add_argument("output", type=Path, nargs="?")
    jma_stations.add_argument("--source-uri", required=True)
    jma_stations.add_argument("--details-html", type=Path)
    jma_stations.add_argument("--details-source-uri")
    jma_stations.add_argument("--allow-issues", action="store_true")
    jma_stations.add_argument("--force", action="store_true")
    _add_output_options(jma_stations)
    _add_address_options(jma_stations)
    jma_stations.set_defaults(handler=convert_jma_stations)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (FileExistsError, OSError, ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
