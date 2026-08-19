"""Organize legacy generated data into creation-date snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _file_date(path: Path) -> tuple[str, str]:
    stat = path.stat()
    if hasattr(stat, "st_birthtime"):
        return datetime.fromtimestamp(stat.st_birthtime).date().isoformat(), "birthtime"
    return datetime.fromtimestamp(stat.st_mtime).date().isoformat(), "mtime"


def plan_moves(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    moves: list[dict[str, str]] = []
    for source in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = source.relative_to(root)
        if relative.parts[0] == "_manifests":
            continue
        # Date-prefixed paths are already in the new layout.
        try:
            datetime.strptime(relative.parts[0], "%Y-%m-%d")
            continue
        except ValueError:
            pass
        created, method = _file_date(source)
        target = root / created / "legacy" / relative
        moves.append({
            "source": str(source), "target": str(target),
            "date": created, "date_source": method,
        })
    return moves


def plan_name_normalization(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    provider_prefixes = {"AIST": "aist", "FDSN": "fdsn", "JMA": "jma", "K-net": "knet"}
    generated_prefixes = {
        "fdsn-events": ("usgs-fdsn-events", ("events-", "event-")),
        "fdsn-stations": ("earthscope-fdsn-stations", ("stations-", "station-")),
        "jma-daily": ("jma-daily-hypocenters", ("daily-",)),
        "jma-intensity": ("jma-monthly-intensity", ()),
        "jshis-flatfile": ("jshis-ground-motion-flatfile", ("flatfile-",)),
    }
    moves: list[dict[str, str]] = []
    for source in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = source.relative_to(root)
        if relative.parts[0] == "_manifests" or source.name in {".DS_Store", ".gitkeep"}:
            continue
        prefix: str | None = None
        removable: tuple[str, ...] = ()
        if len(relative.parts) >= 4 and relative.parts[1] == "legacy":
            prefix = provider_prefixes.get(relative.parts[2])
        elif len(relative.parts) >= 4:
            generated = generated_prefixes.get(relative.parts[1])
            if generated:
                prefix, removable = generated
        if not prefix or source.name.lower().startswith(prefix + "-"):
            continue
        stem, suffix = source.stem, source.suffix
        if stem.lower().startswith(prefix + "_"):
            stem = stem[len(prefix) + 1:]
        for candidate in removable:
            if stem.lower() == candidate.rstrip("-"):
                stem = ""
                break
            if stem.lower().startswith(candidate):
                stem = stem[len(candidate):]
                break
        stem = stem.replace("_", "-")
        target_name = f"{prefix}{f'-{stem}' if stem else ''}{suffix}"
        target = source.with_name(target_name)
        moves.append({
            "source": str(source), "target": str(target),
            "date": relative.parts[0], "date_source": "existing-layout",
        })
    return moves


def apply_moves(root: Path, moves: list[dict[str, str]], operation: str = "organization") -> Path:
    for item in moves:
        target = Path(item["target"])
        if target.exists():
            raise FileExistsError(f"organization target already exists: {target}")
    for item in moves:
        source, target = Path(item["source"]), Path(item["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        if directory.name != "_manifests":
            try:
                directory.rmdir()
            except OSError:
                pass
    manifest = root / "_manifests" / f"{operation}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_name(f".{manifest.name}.tmp")
    payload = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "moves": moves}
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Organize data files by filesystem creation date")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--apply", action="store_true", help="perform moves; the default only prints the plan")
    parser.add_argument("--normalize-names", action="store_true", help="prefix dated files with provider and dataset names")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.root.is_dir():
            raise ValueError(f"data root does not exist: {args.root}")
        moves = plan_name_normalization(args.root) if args.normalize_names else plan_moves(args.root)
        if not args.apply:
            for item in moves:
                print(json.dumps(item, ensure_ascii=False))
            print(f"planned={len(moves)}", file=sys.stderr)
            return 0
        operation = "name-normalization" if args.normalize_names else "organization"
        manifest = apply_moves(args.root.resolve(), moves, operation)
        print(json.dumps({"moved": len(moves), "manifest": str(manifest)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
