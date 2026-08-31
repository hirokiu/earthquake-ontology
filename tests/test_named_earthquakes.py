from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from pyshacl import validate
from rdflib import Dataset, Graph, Literal, RDF, URIRef, XSD

from earthquake_ontology.named_earthquakes import (
    LIST_URL, build_candidates, build_graph, diff_records, normalize_text,
    parse_named_earthquakes, stable_slug, confirm_membership, write_qlever_artifacts,
)
from earthquake_ontology.namespaces import DCTERMS, JPE, SCHEMA


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/jma_named/meishou_ichiran.html"


class NamedEarthquakeTest(unittest.TestCase):
    def test_saved_html_happy_path_and_noto_series(self):
        records = parse_named_earthquakes(FIXTURE.read_bytes())
        self.assertEqual(len(records), 34)
        noto = next(item for item in records if item.name == "令和6年能登半島地震")
        self.assertEqual((noto.activity_type, noto.start_date), ("series", "2020-12"))

    def test_structure_changes_and_empty_table_fail(self):
        good = FIXTURE.read_text(encoding="utf-8")
        for broken in (
            good.replace('<h2 id="jishin">地震現象</h2>', '<h2 id="jishin">別表</h2>'),
            good.replace("期間・現象等※", "期間"),
            '<h2>地震現象</h2><table><tr><th>番号</th><th>名称</th><th>期間・現象等※</th><th>「地域独自の名称等」、主な被害</th></tr></table>',
        ):
            with self.assertRaises(ValueError): parse_named_earthquakes(broken.encode())

    def test_normalization_and_uri_are_deterministic(self):
        self.assertEqual(normalize_text(" 令和６年\u3000能登\n半島&amp;地震 "), "令和6年 能登 半島&地震")
        self.assertEqual(stable_slug("令和６年能登半島地震"), stable_slug("令和6年能登半島地震"))

    def test_rdf_syntax_shacl_and_disaster_separation(self):
        graph = build_graph(parse_named_earthquakes(FIXTURE.read_bytes()))
        serialized = graph.serialize(format="turtle"); reparsed = Graph().parse(data=serialized, format="turtle")
        self.assertEqual(len(graph), len(reparsed))
        self.assertNotIn(Literal("阪神・淡路大震災", lang="ja"), set(graph.objects(None, URIRef("http://www.w3.org/2004/02/skos/core#altLabel"))))
        conforms, _, report = validate(graph, shacl_graph=Graph().parse(ROOT / "shapes/named-earthquake-activity-shapes.ttl"), advanced=True)
        self.assertTrue(conforms, report)

    def test_invalid_shacl_fixtures(self):
        activity = URIRef("https://example.test/activity"); member = URIRef("https://example.test/earthquake")
        membership = URIRef("https://example.test/membership"); graph = Graph()
        graph.add((activity, RDF.type, JPE.NamedEarthquakeActivity)); graph.add((activity, SCHEMA.name, Literal("東日本大震災", lang="ja")))
        graph.add((activity, JPE.namedBy, URIRef("https://www.jma.go.jp/"))); graph.add((activity, DCTERMS.source, URIRef(LIST_URL)))
        graph.add((activity, SCHEMA.startDate, Literal("2024-02-01", datatype=XSD.date))); graph.add((activity, SCHEMA.endDate, Literal("2024-01-01", datatype=XSD.date)))
        graph.add((membership, RDF.type, JPE.EarthquakeActivityMembership)); graph.add((membership, JPE.earthquakeActivity, activity))
        graph.add((membership, JPE.memberEarthquake, member)); graph.add((membership, JPE.membershipStatus, JPE.Candidate))
        graph.add((membership, JPE.membershipMethod, URIRef("https://example.test/method"))); graph.add((membership, DCTERMS.source, URIRef(LIST_URL)))
        graph.add((membership, JPE.confidenceScore, Literal("1.1", datatype=XSD.decimal))); graph.add((activity, SCHEMA.subEvent, member))
        conforms, _, _ = validate(graph, shacl_graph=Graph().parse(ROOT / "shapes/named-earthquake-activity-shapes.ttl"), advanced=True)
        self.assertFalse(conforms)

    def test_diff_and_candidate_does_not_assert_containment(self):
        records = parse_named_earthquakes(FIXTURE.read_bytes())
        previous = [json.loads(json.dumps(records[0].__dict__, ensure_ascii=False))]
        self.assertEqual(len(diff_records(previous, records)["added"]), 33)
        catalog = Graph(); hypo = URIRef("https://seismic.balog.jp/resource/A20240101000000")
        catalog.add((hypo, RDF.type, JPE.hypocenter)); catalog.add((hypo, JPE.originTime, Literal("2026-07-28T16:10:00+09:00", datatype=XSD.dateTime)))
        candidates = build_candidates(records, catalog, "fixture-v1", "2026-08-31T00:00:00+00:00")
        self.assertEqual(len(list(candidates.subjects(RDF.type, JPE.EarthquakeActivityMembership))), 1)
        self.assertEqual(len(list(candidates.triples((None, SCHEMA.subEvent, None)))), 0)
        self.assertEqual(len(list(candidates.triples((None, JPE.hasMemberEarthquake, None)))), 0)
        membership = next(candidates.subjects(RDF.type, JPE.EarthquakeActivityMembership))
        confirm_membership(candidates, membership)
        self.assertEqual(candidates.value(membership, JPE.membershipStatus), JPE.Confirmed)
        self.assertEqual(len(list(candidates.triples((None, SCHEMA.subEvent, None)))), 1)

    def test_writes_qlever_nquads_and_insert_update(self):
        graph = build_graph(parse_named_earthquakes(FIXTURE.read_bytes()))
        with tempfile.TemporaryDirectory() as directory:
            ttl = Path(directory) / "named.ttl"; update = Path(directory) / "insert.ru"
            nq = write_qlever_artifacts(graph, ttl, "https://example.test/graph", update)
            dataset = Dataset().parse(nq, format="nquads")
            self.assertEqual(len(dataset), len(graph))
            text = update.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("INSERT DATA { GRAPH <https://example.test/graph>"))
            self.assertIn("NamedEarthquakeActivity", text)


if __name__ == "__main__": unittest.main()
