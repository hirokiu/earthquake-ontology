from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import httpx

from earthquake_ontology.address_enrichment import GsiAddressEnricher, parse_municipalities
from earthquake_ontology.model import Station, StationAddress


class AddressEnrichmentTest(unittest.TestCase):
    def station(self, address=None):
        return Station(
            uri="https://example.test/station/1", identifier="S001",
            latitude=Decimal("43.0618"), longitude=Decimal("141.3545"),
            source_uri="https://example.test/stations", address=address,
        )

    def test_parses_gsi_municipality_javascript(self):
        mapping = parse_municipalities("GSI.MUNI_ARRAY[1101] = '1,北海道,1101,札幌市　中央区';")
        self.assertEqual(mapping["01101"]["prefecture_code"], "01")
        self.assertEqual(mapping["01101"]["municipality"], "札幌市中央区")

    def test_enriches_and_reuses_persistent_cache(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/muni.js"):
                return httpx.Response(200, text="GSI.MUNI_ARRAY[1101] = '1,北海道,1101,札幌市　中央区';", request=request)
            return httpx.Response(200, json={"results": {"muniCd": "01101", "lv01Nm": "北1条西2丁目"}}, request=request)

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "addresses.json"
            client = httpx.Client(transport=httpx.MockTransport(handler))
            enricher = GsiAddressEnricher(cache, client=client, sleep=lambda _value: None)
            stations, summary = enricher.enrich([self.station()])
            self.assertEqual(stations[0].address.full_address, "北海道札幌市中央区")
            self.assertEqual(stations[0].address.municipality_code, "01101")
            self.assertEqual(summary.enriched, 1)
            self.assertTrue(cache.exists())
            request_count = len(requests)

            cached_enricher = GsiAddressEnricher(cache, client=client, sleep=lambda _value: None)
            cached, cached_summary = cached_enricher.enrich([self.station()])
            self.assertEqual(cached[0].address.full_address, "北海道札幌市中央区")
            self.assertEqual(cached_summary.cache_hits, 1)
            self.assertEqual(len(requests), request_count)

    def test_keeps_existing_address_without_network(self):
        def fail(_request):
            raise AssertionError("network must not be called")

        with tempfile.TemporaryDirectory() as directory:
            client = httpx.Client(transport=httpx.MockTransport(fail))
            address = StationAddress(full_address="既存住所")
            enriched, summary = GsiAddressEnricher(Path(directory) / "cache.json", client=client).enrich([self.station(address)])
        self.assertIs(enriched[0].address, address)
        self.assertEqual(summary.already_present, 1)

    def test_clear_cache_keeps_recoverable_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "addresses.json"
            cache.write_text('{"schema_version": 1, "municipalities": {"old": {}}, "entries": {"old": {}}}\n')
            client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500)))
            enricher = GsiAddressEnricher(cache, client=client)
            backup = enricher.clear_cache()
            self.assertTrue(backup.exists())
            self.assertIn('"old"', backup.read_text())
            self.assertEqual(enricher.cache["municipalities"], {})
            self.assertEqual(enricher.cache["entries"], {})
            self.assertTrue(cache.exists())


if __name__ == "__main__":
    unittest.main()
