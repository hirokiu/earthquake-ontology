from io import StringIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from earthquake_ontology.audit import audit_stream


class AuditStreamTest(unittest.TestCase):
    def codes(self, turtle: str, require_source: bool = False) -> list[str]:
        return [item.code for item in audit_stream(StringIO(turtle), require_source=require_source)]

    def test_detects_current_dataset_errors(self) -> None:
        turtle = """\
<https://example.org/event with-space> a jpe:hypocenter ;
    jpe:magnitude nan ;
    jpe:originTime "2019-01-01 00:00:00+09:00" .
<https://example.org/observation> a jpe:observedWave ;
    jpe:shindo C ;
    rdfs:labal "label" .
"""
        self.assertEqual(
            self.codes(turtle),
            ["IRI_WHITESPACE", "INVALID_NUMERIC", "UNTYPED_DATETIME", "BARE_SYMBOL", "MISSPELLED_VOCABULARY"],
        )

    def test_accepts_typed_and_sourced_record(self) -> None:
        turtle = """\
<https://example.org/event> a jpe:hypocenter ;
    jpe:originTime "2019-01-01T00:00:00+09:00"^^xsd:dateTime ;
    prov:wasDerivedFrom <https://provider.example/event/1> .
"""
        self.assertEqual(self.codes(turtle, require_source=True), [])

    def test_reports_missing_source_when_requested(self) -> None:
        turtle = "<https://example.org/event> a jpe:hypocenter .\n"
        self.assertEqual(self.codes(turtle, require_source=True), ["MISSING_SOURCE"])


if __name__ == "__main__":
    unittest.main()
