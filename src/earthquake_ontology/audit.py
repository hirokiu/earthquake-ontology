"""Streaming checks for common errors in generated Turtle files.

The checks deliberately avoid loading the complete RDF graph so multi-gigabyte
datasets can be inspected with bounded memory. A standards-compliant RDF parser
and SHACL validation remain required before publication.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, TextIO


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    message: str
    text: str


CHECKS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "IRI_WHITESPACE",
        re.compile(r"<[^>]*\s+[^>]*>"),
        "IRI contains whitespace",
    ),
    (
        "INVALID_NUMERIC",
        re.compile(r"\b(?:jpe:(?:magnitude|depth|calcShindo)|schema:(?:latitude|longitude))\s+(?:nan|[-+]?inf|/\./)\s*[;.]", re.IGNORECASE),
        "numeric property has a non-RDF numeric value",
    ),
    (
        "BARE_SYMBOL",
        re.compile(r"\bjpe:(?:shindo|magnitudeType|determinatedWay)\s+[A-Za-z]+\s*[;.]") ,
        "string-like value is not quoted or represented by an IRI",
    ),
    (
        "MISSPELLED_VOCABULARY",
        re.compile(r"\b(?:rdfs:labal|skos:(?:pref|alt)Labal|jpe:sobservationNetwork)\b"),
        "known misspelled vocabulary term",
    ),
    (
        "UNTYPED_DATETIME",
        re.compile(r"\b(?:jpe:originTime|schema:startTime)\s+\"[^\"]+\"\s*[;.](?!\^\^xsd:dateTime)"),
        "date/time literal is not explicitly typed as xsd:dateTime",
    ),
)

RECORD_START = re.compile(
    r"^\s*<[^>]+>\s+(?:a|rdf:type)\s+jpe:(?:hypocenter|observedWave|observer)\b"
)
SOURCE_LINK = re.compile(r"\b(?:dcterms:source|prov:wasDerivedFrom)\b")


def iter_turtle_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Yield Turtle files under files or directories in deterministic order."""
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(item for item in path.rglob("*.ttl") if item.is_file())
        elif path.is_file():
            found.add(path)
    yield from sorted(found)


def audit_stream(
    stream: TextIO, path: str = "<stream>", require_source: bool = False
) -> Iterator[Finding]:
    """Inspect one Turtle stream without constructing an in-memory RDF graph."""
    record_line: int | None = None
    record_text = ""
    record_has_source = False

    for number, raw_line in enumerate(stream, 1):
        line = raw_line.rstrip("\n")
        if RECORD_START.search(line):
            if require_source and record_line is not None and not record_has_source:
                yield Finding(path, record_line, "MISSING_SOURCE", "resource has no source URI", record_text)
            record_line = number
            record_text = line.strip()
            record_has_source = False

        if record_line is not None and SOURCE_LINK.search(line):
            record_has_source = True

        for code, pattern, message in CHECKS:
            if pattern.search(line):
                yield Finding(path, number, code, message, line.strip())

    if require_source and record_line is not None and not record_has_source:
        yield Finding(path, record_line, "MISSING_SOURCE", "resource has no source URI", record_text)


def audit_file(path: Path, require_source: bool = False) -> Iterator[Finding]:
    with path.open(encoding="utf-8", errors="replace") as stream:
        yield from audit_stream(stream, str(path), require_source=require_source)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream-audit generated Turtle files")
    parser.add_argument("paths", nargs="+", type=Path, help="Turtle file or directory")
    parser.add_argument("--require-source", action="store_true", help="report resources without dcterms:source or prov:wasDerivedFrom")
    parser.add_argument("--json", action="store_true", help="write findings as JSON Lines")
    parser.add_argument("--max-findings", type=int, default=1000, help="stop after this many findings (0 means unlimited)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count = 0
    for path in iter_turtle_files(args.paths):
        for finding in audit_file(path, require_source=args.require_source):
            if args.json:
                print(json.dumps(asdict(finding), ensure_ascii=False))
            else:
                print(f"{finding.path}:{finding.line}: {finding.code}: {finding.message}: {finding.text}")
            count += 1
            if args.max_findings and count >= args.max_findings:
                return 1
    return 1 if count else 0


if __name__ == "__main__":
    raise SystemExit(main())
