from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from rdflib import Graph, RDF, URIRef

from earthquake_ontology.cli import main as cli_main
from earthquake_ontology.namespaces import JPE
from earthquake_ontology.parsers import JmaDailyHypocenterParser, JshisFlatFileParser
from earthquake_ontology.rdf_builder import RdfBuilder


class NewSourcesTest(unittest.TestCase):
    def test_jma_daily_html(self):
        html = """<html><pre>
2026  8 17 12:34 56.7  35°30.0'N 139°45.0'E  10  3.2  東京都多摩東部
</pre></html>"""
        parsed = JmaDailyHypocenterParser("https://example.test/20260817.html").parse_html(html)
        self.assertEqual(parsed.issues, [])
        self.assertEqual(len(parsed.hypocenters), 1)
        self.assertEqual(str(parsed.hypocenters[0].latitude), "35.5")
        self.assertEqual(str(parsed.hypocenters[0].depth_m), "10000")

    def test_jshis_zip_core_tables(self):
        site = "siteid2\tstart_date\tend_date\tsite_code\tsite_name\tlon\tlat\televation\tobs_network_id\taddress\tpref_name\tpref_code\tcity_name\tcity_code\nS001\t2000-01-01\t\tAAA\t試験点\t139.1\t35.1\t20\t1\t東京都千代田区\t東京都\t13\t千代田区\t13101\n"
        source = "eq_source_id\tjem_origin_time\tjem_lat\tjem_lon\tjem_depth\tmjma\teq_event_name\nE001\t2024-01-02 03:04:05.6\t35.2\t139.2\t12\t5.1\t試験地震\n"
        record = "smrec_id\tfilebasename\tsite_id\teq_source_id\tlength\tsamplefreq\tmaxacc0\tmaxacc1\tmaxacc2\tmaxvel0\tmaxvel1\tmaxvel2\tsival\tsindo\tfault_dist\nR001\twave\tS001\tE001\t6000\t100\t1.1\t2.2\t3.3\t0.1\t0.2\t0.3\t4.4\t3.5\t22\n"
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "flat.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("flat/site_schema.tsv", site)
                output.writestr("flat/source_schema.tsv", source)
                output.writestr("flat/smrec_schema.tsv", record)
            parsed = JshisFlatFileParser("https://example.test/flat.zip").parse_zip(archive)
        self.assertEqual(parsed.issues, [])
        self.assertEqual((len(parsed.stations), len(parsed.hypocenters), len(parsed.strong_motion_records)), (1, 1, 1))
        graph = RdfBuilder().build_dataset(parsed)
        source_uri = URIRef("https://seismic.balog.jp/resource/jshis/source/E001")
        self.assertEqual(str(graph.value(source_uri, JPE.originTime)), "2024-01-02T03:04:05.600000+09:00")
        record_uri = URIRef("https://seismic.balog.jp/resource/jshis/record/R001")
        self.assertIn((record_uri, RDF.type, JPE.StrongMotionRecord), graph)
        self.assertEqual(str(graph.value(record_uri, JPE.instrumentalIntensity)), "3.5")
        station_uri = URIRef("https://seismic.balog.jp/resource/jshis/station/S001")
        self.assertEqual(str(graph.value(station_uri, URIRef("http://schema.org/address"))), "東京都千代田区")
        self.assertEqual(str(graph.value(station_uri, URIRef("http://imi.go.jp/ns/core/rdf#都道府県コード"))), "13")

    def test_jshis_record_history_id_resolves_to_siteid2(self):
        site = "siteid2\tstart_date\tend_date\tsite_name\tlon\tlat\televation\tobs_network_id\n1104411\t1996-01-01\t\t山崎\t134.5\t35.0\t90\t1\n"
        source = "eq_source_id\tjem_origin_time\tjem_lat\tjem_lon\tjem_depth\tmjma\n326\t1996-05-11 11:46:00\t35.0\t134.5\t10\t4.0\n"
        record = "smrec_id\tfilebasename\tsite_id\teq_source_id\tlength\tsamplefreq\n456041\tHYG012\t11044111\t326\t5900\t100\n"
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "flat.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("site_schema.tsv", site)
                output.writestr("source_schema.tsv", source)
                output.writestr("smrec_schema.tsv", record)
            parsed = JshisFlatFileParser("https://example.test/flat.zip").parse_zip(archive)
        self.assertEqual(
            parsed.strong_motion_records[0].station_uri,
            "https://seismic.balog.jp/resource/jshis/station/1104411",
        )

    def test_jshis_cli_writes_complete_and_yearly_files(self):
        site = "siteid2\tstart_date\tend_date\tsite_name\tlon\tlat\televation\tobs_network_id\nS001\t2000-01-01\t\t試験点\t139.1\t35.1\t20\t1\n"
        source = "eq_source_id\tjem_origin_time\tjem_lat\tjem_lon\tjem_depth\tmjma\teq_event_name\nE2023\t2023-12-31 23:59:59\t35.2\t139.2\t12\t5.1\t地震A\nE2024\t2024-01-02 03:04:05\t35.3\t139.3\t10\t4.2\t地震B\n"
        record = "smrec_id\tfilebasename\tsite_id\teq_source_id\tlength\tsamplefreq\nR2023\twave-a\tS001\tE2023\t100\t100\nR2024\twave-b\tS001\tE2024\t100\t100\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "flatfile-vtest.zip"
            output = root / "jshis.ttl"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("site_schema.tsv", site)
                target.writestr("source_schema.tsv", source)
                target.writestr("smrec_schema.tsv", record)
            status = cli_main([
                "jshis-flatfile", str(archive), str(output),
                "--source-uri", "https://example.test/flat.zip", "--split-by-year",
                "--split-by-entity",
            ])
            self.assertEqual(status, 0)
            complete = Graph().parse(root / "jshis-hypocenters.ttl", format="turtle")
            year_2023 = Graph().parse(root / "jshis-2023-hypocenters.ttl", format="turtle")
            year_2024 = Graph().parse(root / "jshis-2024-hypocenters.ttl", format="turtle")
            self.assertTrue((root / "jshis-stations.ttl").exists())
            self.assertTrue((root / "jshis-observed-waves.ttl").exists())
            self.assertFalse(output.exists())
        self.assertIn((URIRef("https://seismic.balog.jp/resource/jshis/source/E2023"), RDF.type, JPE.hypocenter), complete)
        self.assertIn((URIRef("https://seismic.balog.jp/resource/jshis/source/E2023"), RDF.type, JPE.hypocenter), year_2023)
        self.assertNotIn((URIRef("https://seismic.balog.jp/resource/jshis/source/E2024"), RDF.type, JPE.hypocenter), year_2023)
        self.assertIn((URIRef("https://seismic.balog.jp/resource/jshis/source/E2024"), RDF.type, JPE.hypocenter), year_2024)

    def test_rejects_unsafe_zip_member(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../site_schema.tsv", "x\n")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP member"):
                JshisFlatFileParser("https://example.test/flat.zip").parse_zip(archive)


if __name__ == "__main__":
    unittest.main()
