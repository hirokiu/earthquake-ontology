from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from earthquake_ontology.parsers import JmaStationCodeParser
from earthquake_ontology.parsers.jma_station_details import merge_jma_station_details


class JmaStationCodeTest(unittest.TestCase):
    def test_parses_euc_jp_station_zip_and_matching_observation_uri(self):
        rows = "1000000\t石狩市花川\t4310\t14119\t199604011200\t\n1010000\t札幌中央区北２条\t4304\t14120\t187699999999\t\n"
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "code_p.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("code_p.dat", rows.encode("euc_jp"))
            parsed = JmaStationCodeParser("https://example.test/code_p.zip").parse_zip(archive)
        self.assertEqual(parsed.issues, [])
        self.assertEqual(parsed.stations[0].uri, "https://seismic.balog.jp/resource/sta-1000000")
        self.assertEqual(str(parsed.stations[0].latitude), "43.16666666666666666666666667")
        self.assertEqual(parsed.stations[1].available_from.year, 1876)

    def test_merges_official_detailed_address_and_region(self):
        rows = "1000000\t石狩市花川\t4310\t14119\t199604011200\t\n"
        html = """<table><tr><th>地域名称</th><th>震度観測点名称</th><th>観測点所在地</th><th>緯度(度)</th><th>緯度(分)</th><th>経度(度)</th><th>経度(分)</th><th>観測開始</th><th>観測終了</th></tr><tr><td>石狩地方北部</td><td>石狩市花川</td><td>石狩市花川北6条1-30-2</td><td>43</td><td>10.3</td><td>141</td><td>18.9</td><td>199604011200</td><td></td></tr></table>"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, details = root / "code_p.zip", root / "details.html"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("code_p.dat", rows.encode("euc_jp"))
            details.write_text(html, encoding="utf-8")
            stations = JmaStationCodeParser("https://example.test/code.zip").parse_zip(archive).stations
            merged = merge_jma_station_details(stations, details, "https://example.test/details")
        self.assertEqual(merged[0].region, "石狩地方北部")
        self.assertEqual(merged[0].address.full_address, "石狩市花川北6条1-30-2")
        self.assertEqual(merged[0].additional_source_uris, ("https://example.test/details",))


if __name__ == "__main__":
    unittest.main()
