from datetime import datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from rdflib import RDF, XSD, URIRef
from rdflib import Graph
from pyshacl import validate

from earthquake_ontology.model import DatasetSnapshot, ParsedDataset, Station, StationAddress
from earthquake_ontology.namespaces import JPE, PROV
from earthquake_ontology.parsers.jma_intensity import HYPO_WIDTHS, OBS_WIDTHS, JmaIntensityParser
from earthquake_ontology.rdf_builder import RdfBuilder
from earthquake_ontology.cli import main as cli_main


def fixed_width(values: list[str], widths: tuple[int, ...]) -> str:
    assert len(values) == len(widths)
    return "".join(value[:width].ljust(width) for value, width in zip(values, widths))


def jma_fixture() -> tuple[str, str]:
    locale = "根室半島南東沖".ljust(20) + "00001" + "K" + "  "
    hypocenter = fixed_width(
        [
            "A", "2019", "01", "01", "04", "04", "2854", "0000",
            "043", "2000", "0000", "0146", "0541", "0000", "05120", "000",
            "3", "2", "V", "  ", " ", "6", "1", " ", "1", " ", " ", " ", "000", locale,
        ],
        HYPO_WIDTHS,
    )
    observation_values = ["" for _ in OBS_WIDTHS]
    observation_values[0] = "1670022"
    observation_values[2] = "01"
    observation_values[3] = "04"
    observation_values[4] = "04"
    observation_values[5] = "470"
    observation_values[7] = "1"
    observation_values[9] = "05"
    observation = fixed_width(observation_values, OBS_WIDTHS)
    return hypocenter, observation


class JmaPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source_uri = "https://www.data.jma.go.jp/example/i2019.dat"
        self.parser = JmaIntensityParser(self.source_uri)

    def test_parses_hypocenter_and_observation_without_pandas(self) -> None:
        hypocenter_line, observation_line = jma_fixture()
        result = self.parser.parse_lines([hypocenter_line, observation_line])

        self.assertEqual(result.issues, [])
        self.assertEqual(len(result.hypocenters), 1)
        self.assertEqual(len(result.observations), 1)
        event = result.hypocenters[0]
        self.assertEqual(event.uri, "https://seismic.balog.jp/resource/A2019010104042854")
        self.assertEqual(event.origin_time.isoformat(), "2019-01-01T04:04:28.540000+09:00")
        self.assertEqual(event.latitude.quantize(Decimal("0.0001")), Decimal("43.3333"))
        self.assertEqual(event.longitude.quantize(Decimal("0.0001")), Decimal("146.0902"))
        self.assertEqual(event.depth_m, Decimal("51200.00"))
        self.assertEqual(event.magnitude, Decimal("3.2"))
        self.assertEqual(event.observed_station_count, 1)
        self.assertEqual(event.determination_method, "気象庁震源")
        self.assertEqual(event.determined_by_uri, "https://www.jma.go.jp/jma/")

        observation = result.observations[0]
        self.assertEqual(observation.calculated_intensity, Decimal("0.5"))
        self.assertEqual(observation.intensity, "震度1")
        self.assertEqual(observation.source_uri, self.source_uri)

    def test_reports_bad_record_instead_of_generating_invalid_rdf(self) -> None:
        hypocenter_line, _ = jma_fixture()
        broken = hypocenter_line[:21] + "///" + hypocenter_line[24:]
        result = self.parser.parse_lines([broken])
        self.assertEqual(result.hypocenters, [])
        self.assertEqual(result.issues[0].code, "MISSING_COORDINATE")

    def test_builds_typed_rdf_with_source_links(self) -> None:
        hypocenter_line, observation_line = jma_fixture()
        result = self.parser.parse_lines([hypocenter_line, observation_line])
        result.stations.append(
            Station(
                uri="https://seismic.balog.jp/resource/sta-1670022",
                identifier="1670022",
                latitude=Decimal("43.33"),
                longitude=Decimal("146.09"),
                source_uri="https://www.data.jma.go.jp/example/stations",
                address=StationAddress(
                    full_address="北海道石狩市", prefecture="北海道",
                    prefecture_code="01", municipality="石狩市", municipality_code="01235",
                ),
            )
        )
        graph = RdfBuilder().build_dataset(result)
        event = URIRef(result.hypocenters[0].uri)
        self.assertIn((event, RDF.type, JPE.hypocenter), graph)
        self.assertIn((event, PROV.wasDerivedFrom, URIRef(self.source_uri)), graph)
        origin = graph.value(event, JPE.originTime)
        self.assertEqual(origin.datatype, XSD.dateTime)
        self.assertEqual(str(origin), "2019-01-01T04:04:28.540000+09:00")
        self.assertEqual(str(graph.value(event, JPE.detarminatedBy)), "https://www.jma.go.jp/jma/")
        station = URIRef("https://seismic.balog.jp/resource/sta-1670022")
        self.assertEqual(str(graph.value(station, URIRef("http://schema.org/address"))), "北海道石狩市")
        self.assertEqual(str(graph.value(station, URIRef("http://imi.go.jp/ns/core/rdf#都道府県"))), "北海道")
        self.assertEqual(str(graph.value(station, URIRef("http://imi.go.jp/ns/core/rdf#市区町村コード"))), "01235")
        root = Path(__file__).parents[1]
        conforms, _, report = validate(
            graph,
            shacl_graph=Graph().parse(root / "shapes/core.shacl.ttl", format="turtle"),
            ont_graph=Graph().parse(root / "ontology/jp-earthquake.ttl", format="turtle"),
            inference="rdfs",
        )
        self.assertTrue(conforms, report)

    def test_builds_snapshot_metadata(self) -> None:
        generated_at = datetime(2026, 8, 19, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        snapshot = DatasetSnapshot(
            uri="https://seismic.balog.jp/snapshot/jma/2019/20260819T030000Z",
            dataset_uri="https://www.data.jma.go.jp/dataset/monthly-intensity",
            source_uri=self.source_uri,
            generated_at=generated_at,
            source_sha256="a" * 64,
            graph_uri="https://seismic.balog.jp/graph/jma/monthly-intensity/2019/20260819T030000Z",
            converter_version="0.1.0",
        )
        graph = RdfBuilder().new_graph()
        subject = RdfBuilder().add_snapshot(graph, snapshot)
        self.assertIn((subject, RDF.type, JPE.DatasetSnapshot), graph)
        self.assertIn((subject, PROV.wasDerivedFrom, URIRef(self.source_uri)), graph)

    def test_conversion_cli_writes_data_and_snapshot_atomically(self) -> None:
        hypocenter_line, observation_line = jma_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "i2019.dat"
            output = root / "i2019.ttl"
            metadata = root / "i2019.snapshot.ttl"
            source.write_text(hypocenter_line + "\n" + observation_line + "\n", encoding="shift_jis")
            status = cli_main([
                "jma-intensity", str(source), str(output),
                "--source-uri", self.source_uri,
                "--snapshot-output", str(metadata),
                "--snapshot-uri", "https://seismic.balog.jp/snapshot/jma/2019/test",
                "--dataset-uri", "https://www.data.jma.go.jp/dataset/monthly-intensity",
                "--graph-uri", "https://seismic.balog.jp/graph/jma/monthly-intensity/2019/test",
            ])
            self.assertEqual(status, 0)
            self.assertTrue(output.exists())
            self.assertTrue(metadata.exists())
            self.assertGreater(len(Graph().parse(output, format="turtle")), 0)
            self.assertGreater(len(Graph().parse(metadata, format="turtle")), 0)


if __name__ == "__main__":
    unittest.main()
