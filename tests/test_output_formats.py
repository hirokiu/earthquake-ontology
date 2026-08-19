from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from rdflib import Dataset, Graph, URIRef

from earthquake_ontology.cli import main as convert_main
from earthquake_ontology.organize_cli import apply_moves, plan_moves, plan_name_normalization
from test_fdsn import QUAKEML


class OutputFormatTest(unittest.TestCase):
    def test_automatic_dated_ntriples_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "events.xml"
            source.write_bytes(QUAKEML)
            status = convert_main([
                "fdsn-events", str(source), "--source-uri", "https://example.test/events.xml",
                "--output-format", "ntriples", "--output-root", str(root / "data"),
                "--created-at", "2026-08-19",
            ])
            output = root / "data/2026-08-19/fdsn-events/ntriples/usgs-fdsn-events.nt"
            self.assertEqual(status, 0)
            self.assertGreater(len(Graph().parse(output, format="nt")), 0)

    def test_nquads_requires_and_uses_named_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "events.xml", root / "events.nq"
            source.write_bytes(QUAKEML)
            self.assertEqual(convert_main([
                "fdsn-events", str(source), str(output),
                "--source-uri", "https://example.test/events.xml",
                "--output-format", "nquads", "--graph-uri", "https://example.test/graph/events",
            ]), 0)
            dataset = Dataset().parse(output, format="nquads")
            self.assertGreater(len(dataset.graph(URIRef("https://example.test/graph/events"))), 0)

    def test_split_by_entity_uses_descriptive_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "events.xml", root / "usgs.ttl"
            source.write_bytes(QUAKEML)
            self.assertEqual(convert_main([
                "fdsn-events", str(source), str(output),
                "--source-uri", "https://example.test/events.xml", "--split-by-entity",
            ]), 0)
            separated = root / "usgs-hypocenters.ttl"
            self.assertTrue(separated.exists())
            self.assertFalse(output.exists())
            self.assertGreater(len(Graph().parse(separated, format="turtle")), 0)

    def test_split_does_not_duplicate_existing_entity_suffix(self):
        from earthquake_ontology.cli import _entity_path

        output = Path("jma-daily-hypocenters-20260818.ttl")
        self.assertEqual(_entity_path(output, "hypocenters"), output)

    def test_turtle_uses_schema_prefix_without_numeric_suffix(self):
        from earthquake_ontology.rdf_builder import RdfBuilder

        graph = RdfBuilder().new_graph()
        graph.add((URIRef("https://example.test/s"), URIRef("http://schema.org/identifier"), URIRef("https://example.test/o")))
        turtle = graph.serialize(format="turtle")
        self.assertIn("@prefix schema:", turtle)
        self.assertNotIn("schema1:", turtle)

    def test_organizer_records_reversible_moves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data"
            source = root / "FDSN/events.ttl"
            source.parent.mkdir(parents=True)
            source.write_text("<s> <p> <o> .\n")
            with patch("earthquake_ontology.organize_cli._file_date", return_value=("2026-05-08", "birthtime")):
                moves = plan_moves(root)
            manifest = apply_moves(root, moves)
            self.assertFalse(source.exists())
            self.assertTrue((root / "2026-05-08/legacy/FDSN/events.ttl").exists())
            self.assertTrue(manifest.exists())
            self.assertEqual(plan_moves(root), [])

    def test_name_normalization_includes_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data"
            source = root / "2026-05-08/legacy/FDSN/event_1970_all.ttl"
            source.parent.mkdir(parents=True)
            source.write_text("<s> <p> <o> .\n")
            moves = plan_name_normalization(root)
            self.assertEqual(Path(moves[0]["target"]).name, "fdsn-event-1970-all.ttl")
            apply_moves(root, moves, "name-normalization")
            self.assertTrue(source.with_name("fdsn-event-1970-all.ttl").exists())


if __name__ == "__main__":
    unittest.main()
