from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from rdflib import RDF, URIRef

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
        site = "siteid2\tstart_date\tend_date\tsite_code\tsite_name\tlon\tlat\televation\tobs_network_id\nS001\t2000-01-01\t\tAAA\t試験点\t139.1\t35.1\t20\t1\n"
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
        record_uri = URIRef("https://seismic.balog.jp/resource/jshis/record/R001")
        self.assertIn((record_uri, RDF.type, JPE.StrongMotionRecord), graph)
        self.assertEqual(str(graph.value(record_uri, JPE.instrumentalIntensity)), "3.5")

    def test_rejects_unsafe_zip_member(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../site_schema.tsv", "x\n")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP member"):
                JshisFlatFileParser("https://example.test/flat.zip").parse_zip(archive)


if __name__ == "__main__":
    unittest.main()
