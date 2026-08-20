"""Build a complete named-graph snapshot from immutable acquisition manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath

from .cli import main as convert_main
from .config import load_settings


GRAPH_URIS = {
    "fdsn_events_usgs": "https://seismic.balog.jp/graph/usgs/fdsn-events",
    "fdsn_stations_earthscope": "https://seismic.balog.jp/graph/earthscope/fdsn-stations",
    "jma_daily_hypocenters": "https://seismic.balog.jp/graph/jma/daily-hypocenters",
    "jma_intensity": "https://seismic.balog.jp/graph/jma/monthly-intensity",
    "jma_intensity_stations": "https://seismic.balog.jp/graph/jma/intensity-stations",
    "jshis_ground_motion_flatfile": "https://seismic.balog.jp/graph/nied/jshis-ground-motion-flatfile",
}


def _manifest_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = list(data.get("artifacts", {}).values())
    return sorted(entries, key=lambda item: (str(item.get("period", "")), str(item.get("url", ""))))


def _safe_zip_members(path: Path, destination: Path) -> list[Path]:
    outputs: list[Path] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if info.is_dir() or member.is_absolute() or ".." in member.parts:
                continue
            if member.suffix.lower() not in {".dat", ".txt"}:
                continue
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            outputs.append(target)
    if not outputs:
        raise ValueError(f"no fixed-width .dat/.txt member found in {path}")
    return sorted(outputs)


def _run_conversion(arguments: list[str]) -> None:
    status = convert_main(arguments)
    if status:
        raise RuntimeError(f"conversion failed ({status}): {' '.join(arguments)}")


def build_snapshot(config_path: Path, snapshot: Path, source_ids: set[str] | None = None) -> int:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    settings = load_settings(config_path)
    output = snapshot.resolve() / "nquads"
    extracted = snapshot.resolve() / "extracted"
    output.mkdir(parents=True, exist_ok=True)
    source_records: list[dict] = []

    details_entry = None
    details_manifest = settings.storage.manifest_directory / "jma_intensity_station_details.json"
    if details_manifest.exists():
        entries = _manifest_entries(details_manifest)
        details_entry = entries[-1] if entries else None

    for source_id, source in settings.sources.items():
        if not source.enabled or source_id == "jma_intensity_station_details":
            continue
        if source_ids and source_id not in source_ids:
            continue
        graph_uri = GRAPH_URIS.get(source_id)
        if not graph_uri:
            raise ValueError(f"no publication graph URI configured for {source_id}")
        manifest_path = settings.storage.manifest_directory / f"{source_id}.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"missing acquisition manifest: {manifest_path}")
        for entry in _manifest_entries(manifest_path):
            input_path = Path(entry["path"])
            period = str(entry["period"])
            source_uri = str(entry["url"])
            base = output / f"{source_id}-{period}.nq"
            common = ["--source-uri", source_uri, "--output-format", "nquads", "--graph-uri", graph_uri, "--split-by-entity"]
            parser = source.parser
            if parser == "fdsn_quakeml":
                _run_conversion(["fdsn-events", str(input_path), str(base), *common])
            elif parser == "fdsn_stationxml":
                _run_conversion(["fdsn-stations", str(input_path), str(base), *common])
            elif parser == "jma_daily_hypocenter_html":
                _run_conversion(["jma-daily", str(input_path), str(base), *common])
            elif parser == "jma_intensity_zip":
                members = _safe_zip_members(input_path, extracted / source_id / period)
                for index, member in enumerate(members, 1):
                    member_output = base if len(members) == 1 else base.with_name(f"{base.stem}-{index}{base.suffix}")
                    _run_conversion(["jma-intensity", str(member), str(member_output), *common])
            elif parser == "jma_station_zip":
                args = ["jma-stations", str(input_path), str(base), *common]
                if details_entry:
                    args.extend(["--details-html", details_entry["path"], "--details-source-uri", details_entry["url"]])
                _run_conversion(args)
            elif parser == "jshis_ground_motion_flatfile_zip":
                _run_conversion(["jshis-flatfile", str(input_path), str(base), *common])
            else:
                raise ValueError(f"unsupported publication parser for {source_id}: {parser}")
            source_records.append({
                "source_id": source_id, "period": period, "url": source_uri,
                "sha256": entry["sha256"], "path": str(input_path), "graph_uri": graph_uri,
            })

    files = sorted(output.glob("*.nq"))
    if not files:
        raise RuntimeError("snapshot produced no N-Quads files")
    manifest = {
        "schema_version": 1,
        "sources": source_records,
        "outputs": [{"path": str(path), "bytes": path.stat().st_size} for path in files],
    }
    (snapshot / "snapshot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"phase": "snapshot", "files": len(files), "bytes": sum(path.stat().st_size for path in files)}))
    return 0


def validate_snapshot(snapshot: Path) -> int:
    manifest_path = snapshot.resolve() / "snapshot-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    graph_counts: dict[str, int] = {}
    for item in manifest.get("outputs", []):
        path = Path(item["path"])
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing or empty output: {path}")
            continue
        with path.open(encoding="utf-8", errors="strict") as stream:
            for number, line in enumerate(stream, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                if not stripped.endswith(" ."):
                    errors.append(f"{path}:{number}: invalid N-Quads line ending")
                    break
                parts = stripped.rsplit(" ", 2)
                if len(parts) < 3 or not parts[-2].startswith("<https://seismic.balog.jp/graph/"):
                    errors.append(f"{path}:{number}: missing publication named graph")
                    break
                graph = parts[-2][1:-1]
                graph_counts[graph] = graph_counts.get(graph, 0) + 1
    required = {
        "https://seismic.balog.jp/graph/jma/monthly-intensity/hypocenters",
        "https://seismic.balog.jp/graph/jma/monthly-intensity/observed-waves",
        "https://seismic.balog.jp/graph/jma/intensity-stations/stations",
        "https://seismic.balog.jp/graph/usgs/fdsn-events/hypocenters",
    }
    missing = required - graph_counts.keys()
    if missing:
        errors.append("required graphs are empty: " + ", ".join(sorted(missing)))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print(json.dumps({"phase": "validate_snapshot", "graphs": graph_counts}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or validate a publication snapshot")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--config", type=Path, default=Path("config/sources.yaml"))
    build.add_argument("--snapshot", type=Path, required=True)
    build.add_argument("--source", action="append", dest="sources")
    validate = sub.add_parser("validate")
    validate.add_argument("--snapshot", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build":
            return build_snapshot(args.config, args.snapshot, set(args.sources) if args.sources else None)
        return validate_snapshot(args.snapshot)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
