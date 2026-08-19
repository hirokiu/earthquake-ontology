"""Parser interface shared by external data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable
from urllib.parse import quote, urlsplit

from earthquake_ontology.model import ParsedDataset


AGENCY_URIS = {
    "JMA": "https://www.jma.go.jp/jma/",
    "気象庁": "https://www.jma.go.jp/jma/",
    "USGS": "https://www.usgs.gov/",
    "NEIC": "https://www.usgs.gov/programs/earthquake-hazards/national-earthquake-information-center-neic",
    "ISC": "https://www.isc.ac.uk/",
    "NIED": "https://www.bosai.go.jp/",
}


def agency_uri(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if urlsplit(value).scheme in {"http", "https"}:
        return value
    return AGENCY_URIS.get(value.upper(), "https://seismic.balog.jp/resource/organization/" + quote(value, safe=""))


class DatasetParser(ABC):
    @abstractmethod
    def parse_lines(self, lines: Iterable[str]) -> ParsedDataset:
        """Parse provider records without performing network or file I/O."""
        raise NotImplementedError
