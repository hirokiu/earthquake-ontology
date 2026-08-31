"""Strict, reproducible processing of the JMA named-earthquake table."""

from __future__ import annotations

import argparse
import hashlib
import html as html_module
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx
from pyshacl import validate
from rdflib import Dataset, Graph, Literal, RDF, SKOS, URIRef, XSD

from .namespaces import DCTERMS, JPE, PROV, SCHEMA

LIST_URL = "https://www.jma.go.jp/jma/kishou/know/meishou/meishou_ichiran.html"
JMA_AGENT = "https://www.jma.go.jp/jma/"
RESOURCE_ROOT = "https://seismic.balog.jp/resource/named-earthquake/"
DISASTER_NAMES = {"阪神・淡路大震災", "東日本大震災", "新潟県中越大震災"}
TYPE_IRIS = {
    "single": JPE.SingleEarthquakeType, "series": JPE.SeriesActivityType,
    "swarm": JPE.SwarmEarthquakeType, "distant-tsunami": JPE.DistantEarthquakeTsunamiType,
    "uncertain": JPE.UncertainActivityType,
}


def normalize_text(value: str) -> str:
    """NFKC plus deterministic whitespace normalization, preserving Japanese text."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", html_module.unescape(value))).strip()


def stable_slug(name: str) -> str:
    normalized = normalize_text(name)
    year = re.search(r"(?:19|20)\d{2}", normalized)
    prefix = year.group(0) if year else "named"
    return f"{prefix}-{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


@dataclass(frozen=True)
class NamedEarthquake:
    ordinal: int
    name_raw: str
    period_raw: str
    description_raw: str
    links: tuple[str, ...]
    name: str
    period: str
    description: str
    uri: str
    activity_type: str
    start_date: str | None
    end_date: str | None
    local_names: tuple[str, ...]
    disaster_names: tuple[str, ...]


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.heading = ""
        self.current_table_heading = ""
        self.in_h2 = self.in_table = self.in_cell = False
        self.heading_parts: list[str] = []
        self.cell_parts: list[str] = []
        self.cell_links: list[str] = []
        self.row: list[tuple[str, tuple[str, ...]]] = []
        self.tables: dict[str, list[list[tuple[str, tuple[str, ...]]]]] = {}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "h2": self.in_h2, self.heading_parts = True, []
        elif tag == "table":
            self.in_table, self.current_table_heading = True, normalize_text("".join(self.heading_parts)) or self.heading
            self.tables.setdefault(self.current_table_heading, [])
        elif tag == "tr" and self.in_table: self.row = []
        elif tag in {"th", "td"} and self.in_table:
            self.in_cell, self.cell_parts, self.cell_links = True, [], []
        elif tag == "br" and self.in_cell: self.cell_parts.append("\n")
        elif tag == "a" and self.in_cell:
            href = dict(attrs).get("href")
            if href: self.cell_links.append(urljoin(LIST_URL, href))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "h2":
            self.in_h2 = False; self.heading = normalize_text("".join(self.heading_parts))
        elif tag in {"th", "td"} and self.in_cell:
            self.row.append(("".join(self.cell_parts).strip(), tuple(self.cell_links))); self.in_cell = False
        elif tag == "tr" and self.in_table and self.row:
            self.tables[self.current_table_heading].append(self.row)
        elif tag == "table": self.in_table = False

    def handle_data(self, data):
        if self.in_h2: self.heading_parts.append(data)
        if self.in_cell: self.cell_parts.append(data)


ERA_START = {"昭和": 1925, "平成": 1988, "令和": 2018}


def _date(text: str) -> str | None:
    match = re.search(r"(昭和|平成|令和)(元|\d+)年(\d+)月(\d+)日", normalize_text(text))
    if not match: return None
    number = 1 if match.group(2) == "元" else int(match.group(2))
    return f"{ERA_START[match.group(1)] + number:04d}-{int(match.group(3)):02d}-{int(match.group(4)):02d}"


def _classify(name: str, period: str, description: str) -> str:
    combined = name + " " + period + " " + description
    if "群発" in combined: return "swarm"
    if "チリ地震津波" in combined: return "distant-tsunami"
    if "一連の地震活動" in combined or "計4回" in combined or "4月14日、4月16日" in combined: return "series"
    if _date(period): return "single"
    return "uncertain"


def parse_named_earthquakes(source: bytes) -> list[NamedEarthquake]:
    parser = _TableParser(); parser.feed(source.decode("utf-8"))
    rows = parser.tables.get("地震現象")
    if not rows: raise ValueError("JMA earthquake table is missing")
    header = [normalize_text(cell[0]).replace("※", "") for cell in rows[0]]
    if len(header) != 4 or header[1:] != ["名称", "期間・現象等", "「地域独自の名称等」、主な被害"]:
        raise ValueError(f"unexpected JMA earthquake columns: {header!r}")
    result, uris = [], set()
    for row in rows[1:]:
        if len(row) != 4: raise ValueError(f"unexpected JMA earthquake row width: {len(row)}")
        raw = [cell[0] for cell in row]; values = [normalize_text(value) for value in raw]
        if not values[0].isdigit() or not values[1]: raise ValueError(f"invalid JMA earthquake row: {values!r}")
        quoted = tuple(re.findall(r"「([^」]+)」", values[3]))
        disasters = tuple(value for value in quoted if value in DISASTER_NAMES or value.endswith("大震災"))
        locals_ = tuple(value for value in quoted if value not in disasters)
        uri = RESOURCE_ROOT + stable_slug(values[1])
        if uri in uris: raise ValueError(f"URI collision: {uri}")
        uris.add(uri)
        start = "2020-12" if values[1] == "令和6年能登半島地震" else _date(values[2])
        result.append(NamedEarthquake(int(values[0]), raw[1], raw[2], raw[3], tuple(link for cell in row for link in cell[1]),
            values[1], values[2], values[3], uri, _classify(values[1], values[2], values[3]), start, None, locals_, disasters))
    if not result: raise ValueError("JMA earthquake table produced zero results")
    return result


def build_graph(records: list[NamedEarthquake], source_uri: str = LIST_URL) -> Graph:
    graph = Graph()
    for prefix, ns in (("dcterms", DCTERMS), ("jpe", JPE), ("prov", PROV), ("schema", SCHEMA), ("skos", SKOS)):
        graph.bind(prefix, ns, override=True, replace=True)
    for record in records:
        subject = URIRef(record.uri)
        graph.add((subject, RDF.type, JPE.NamedEarthquakeActivity)); graph.add((subject, RDF.type, SCHEMA.EventSeries))
        graph.add((subject, SCHEMA.name, Literal(record.name, lang="ja"))); graph.add((subject, SKOS.prefLabel, Literal(record.name, lang="ja")))
        graph.add((subject, JPE.namedBy, URIRef(JMA_AGENT))); graph.add((subject, DCTERMS.source, URIRef(source_uri)))
        graph.add((subject, JPE.activityType, TYPE_IRIS[record.activity_type]))
        if record.start_date:
            datatype = XSD.gYearMonth if len(record.start_date) == 7 else XSD.date
            graph.add((subject, SCHEMA.startDate, Literal(record.start_date, datatype=datatype)))
        for name in record.local_names: graph.add((subject, SKOS.altLabel, Literal(name, lang="ja")))
        for name in record.disaster_names:
            disaster = URIRef("https://seismic.balog.jp/resource/disaster/" + stable_slug(name))
            graph.add((disaster, RDF.type, JPE.DisasterCase)); graph.add((disaster, SCHEMA.name, Literal(name, lang="ja")))
            graph.add((subject, JPE.causedDisaster, disaster))
    return graph


def diff_records(previous: list[dict], current: list[NamedEarthquake]) -> dict:
    before = {item["uri"]: item for item in previous}; after = {item.uri: asdict(item) for item in current}
    return {"added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()),
            "modified": sorted(uri for uri in before.keys() & after.keys() if before[uri] != after[uri])}


def write_qlever_artifacts(graph: Graph, turtle_path: Path, graph_uri: str, update_path: Path | None = None) -> Path:
    """Write Turtle plus a named-graph N-Quads file and optional SPARQL INSERT DATA."""
    turtle_path.write_text(graph.serialize(format="turtle").rstrip() + "\n", encoding="utf-8")
    nquads_path = turtle_path.with_suffix(".nq")
    graph_ref = URIRef(graph_uri)
    nt_lines = sorted(f"{s.n3()} {p.n3()} {o.n3()} ." for s, p, o in graph)
    nq_lines = [f"{line[:-2]} {graph_ref.n3()} ." for line in nt_lines]
    nquads_path.write_text("\n".join(nq_lines) + "\n", encoding="utf-8")
    if update_path is not None:
        triples = "\n".join(nt_lines) + "\n"
        update_path.write_text(f"INSERT DATA {{ GRAPH <{graph_uri}> {{\n{triples}}} }}\n", encoding="utf-8")
    return nquads_path


def build_candidates(records: list[NamedEarthquake], catalog: Graph, catalog_version: str, generated_at: str, source_uri: str = LIST_URL) -> Graph:
    """Generate conservative temporal candidates; never confirmed containment triples."""
    graph = Graph(); graph.bind("jpe", JPE); graph.bind("dcterms", DCTERMS); graph.bind("prov", PROV)
    for record in records:
        if not record.start_date or len(record.start_date) != 10: continue
        for hypocenter in catalog.subjects(RDF.type, JPE.hypocenter):
            origin = catalog.value(hypocenter, JPE.originTime)
            if origin is None or str(origin)[:10] != record.start_date: continue
            earthquake = URIRef("https://seismic.balog.jp/resource/earthquake/" + str(hypocenter).rsplit("/", 1)[-1])
            digest = hashlib.sha256(f"{record.uri}|{earthquake}".encode()).hexdigest()[:24]
            membership = URIRef(f"https://seismic.balog.jp/resource/membership/{digest}")
            method = URIRef("https://seismic.balog.jp/method/activity-membership/single-date-v1")
            for triple in ((membership, RDF.type, JPE.EarthquakeActivityMembership), (membership, JPE.earthquakeActivity, URIRef(record.uri)),
                           (membership, JPE.memberEarthquake, earthquake), (membership, JPE.membershipStatus, JPE.Candidate),
                           (membership, JPE.membershipRole, JPE.Unclassified), (membership, JPE.membershipMethod, method),
                           (membership, DCTERMS.source, URIRef(source_uri))): graph.add(triple)
            graph.add((membership, JPE.confidenceScore, Literal(Decimal("0.50"), datatype=XSD.decimal)))
            graph.add((membership, JPE.catalogVersion, Literal(catalog_version))); graph.add((membership, JPE.ruleVersion, Literal("single-date-v1")))
            graph.add((membership, JPE.timeWindow, Literal(record.start_date))); graph.add((membership, JPE.threshold, Literal("same JST calendar date")))
            graph.add((membership, PROV.generatedAtTime, Literal(generated_at, datatype=XSD.dateTime)))
            graph.add((URIRef(record.uri), JPE.hasMembership, membership))
            graph.add((earthquake, RDF.type, JPE.earthquake)); graph.add((earthquake, JPE.hasHypocenter, hypocenter))
    return graph


def confirm_membership(graph: Graph, membership: URIRef) -> None:
    """Record human/official confirmation and materialize containment consistently."""
    activity = graph.value(membership, JPE.earthquakeActivity)
    earthquake = graph.value(membership, JPE.memberEarthquake)
    if activity is None or earthquake is None:
        raise ValueError("membership lacks activity or member")
    graph.set((membership, JPE.membershipStatus, JPE.Confirmed))
    graph.add((activity, JPE.hasMemberEarthquake, earthquake)); graph.add((activity, SCHEMA.subEvent, earthquake))
    graph.add((earthquake, JPE.isMemberOfEarthquakeActivity, activity)); graph.add((earthquake, SCHEMA.superEvent, activity))


def fetch(url: str, destination: Path, metadata: Path) -> None:
    response = httpx.get(url, follow_redirects=True, timeout=30, headers={"User-Agent": "earthquake-ontology/0.1"}); response.raise_for_status()
    if not response.content: raise ValueError("empty HTTP response")
    destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(response.content)
    info = {"url": str(response.url), "retrieved_at": datetime.now(timezone.utc).isoformat(), "status_code": response.status_code,
            "http_headers": dict(response.headers), "bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest()}
    metadata.write_text(json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch"); p.add_argument("output", type=Path); p.add_argument("--metadata", type=Path, required=True); p.add_argument("--url", default=LIST_URL)
    p = sub.add_parser("convert"); p.add_argument("input", type=Path); p.add_argument("output", type=Path); p.add_argument("--json", type=Path); p.add_argument("--previous", type=Path); p.add_argument("--diff", type=Path)
    p.add_argument("--graph-uri", default="https://seismic.balog.jp/graph/jma/named-earthquakes/20260831")
    p.add_argument("--update", type=Path, help="also write a SPARQL INSERT DATA file")
    p = sub.add_parser("candidates"); p.add_argument("input", type=Path); p.add_argument("catalog", type=Path); p.add_argument("output", type=Path); p.add_argument("--catalog-version", required=True); p.add_argument("--generated-at", required=True)
    args = parser.parse_args(argv)
    if args.command == "fetch": fetch(args.url, args.output, args.metadata); return 0
    records = parse_named_earthquakes(args.input.read_bytes())
    if args.command == "convert":
        write_qlever_artifacts(build_graph(records), args.output, args.graph_uri, args.update)
        if args.json: args.json.write_text(json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.diff:
            previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else []
            args.diff.write_text(json.dumps(diff_records(previous, records), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    catalog = Graph().parse(args.catalog)
    build_candidates(records, catalog, args.catalog_version, args.generated_at).serialize(args.output, format="turtle"); return 0


if __name__ == "__main__": raise SystemExit(main())
