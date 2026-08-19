from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from earthquake_ontology.acquisition import DataFetcher
from earthquake_ontology.config import load_settings
from earthquake_ontology.parsers import FdsnQuakeMlParser, FdsnStationXmlParser

ROOT = Path(__file__).parents[1]

QUAKEML = b'''<?xml version="1.0"?>
<q:quakeml xmlns:q="http://quakeml.org/xmlns/quakeml/1.2" xmlns="http://quakeml.org/xmlns/bed/1.2">
 <eventParameters><event publicID="smi:service.iris.edu/fdsnws/event/1/query?eventid=1697888">
  <preferredOriginID>smi:origin/2</preferredOriginID><preferredMagnitudeID>smi:mag/2</preferredMagnitudeID>
  <description><text>INDIAN OCEAN TRIPLE JUNCTION</text><type>region name</type></description>
  <origin publicID="smi:origin/1"><time><value>2000-01-01T00:00:00Z</value></time><latitude><value>0</value></latitude><longitude><value>0</value></longitude></origin>
  <origin publicID="smi:origin/2"><time><value>2003-12-31T23:51:57.76Z</value></time><latitude><value>-25.742</value></latitude><longitude><value>69.6962</value></longitude><depth><value>10000</value></depth><creationInfo><agencyID>ISC</agencyID></creationInfo></origin>
  <magnitude publicID="smi:mag/2"><mag><value>4.9</value></mag><type>mb</type><creationInfo><agencyID>NEIC</agencyID></creationInfo></magnitude>
 </event></eventParameters>
</q:quakeml>'''

STATIONXML = b'''<?xml version="1.0"?>
<FDSNStationXML xmlns="http://www.fdsn.org/xml/station/1"><Network code="IU">
 <Station code="ANMO" startDate="1990-01-01T00:00:00Z"><Latitude>34.9459</Latitude><Longitude>-106.4572</Longitude><Elevation>1850</Elevation><Site><Name>Albuquerque</Name></Site></Station>
</Network></FDSNStationXML>'''


class FdsnTest(unittest.TestCase):
    def test_quakeml_preferred_values_and_legacy_uri(self):
        parsed = FdsnQuakeMlParser("https://example.test/query.xml").parse_bytes(QUAKEML)
        self.assertEqual(parsed.issues, [])
        event = parsed.hypocenters[0]
        self.assertEqual(event.uri, "http://service.iris.edu/fdsnws/event/1/query?eventid=1697888")
        self.assertEqual(event.latitude, Decimal("-25.742"))
        self.assertEqual(event.magnitude, Decimal("4.9"))
        self.assertEqual(event.catalog, "ISC")
        self.assertEqual(event.determination_method, "NEIC")

    def test_stationxml_uses_existing_station_uri_shape(self):
        parsed = FdsnStationXmlParser("https://example.test/stations.xml").parse_bytes(STATIONXML)
        self.assertEqual(parsed.issues, [])
        station = parsed.stations[0]
        self.assertEqual(station.uri, "https://seismic.balog.jp/resource/sta-FDSN-IU.ANMO")
        self.assertEqual(station.identifier, "IU.ANMO")
        self.assertEqual(station.label_en, "Albuquerque")

    def test_negative_depth_is_preserved(self):
        xml = QUAKEML.replace(b"<value>10000</value></depth>", b"<value>-1200</value></depth>")
        event = FdsnQuakeMlParser("https://example.test/query.xml").parse_bytes(xml).hypocenters[0]
        self.assertEqual(event.depth_m, Decimal("-1200"))

    def test_yearly_fdsn_queries_are_generated_from_yaml(self):
        settings = load_settings(ROOT / "config/sources.yaml")
        source = settings.sources["fdsn_events_usgs"]
        with DataFetcher(settings) as fetcher:
            artifacts = fetcher.discover("fdsn_events_usgs", source)
        self.assertEqual(artifacts[0].period, "1960")
        self.assertIn("starttime=1960-01-01", artifacts[0].url)
        self.assertIn("minmagnitude=3.0", artifacts[0].url)


if __name__ == "__main__":
    unittest.main()
