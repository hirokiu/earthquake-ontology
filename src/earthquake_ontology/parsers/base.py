"""Parser interface shared by external data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from earthquake_ontology.model import ParsedDataset


class DatasetParser(ABC):
    @abstractmethod
    def parse_lines(self, lines: Iterable[str]) -> ParsedDataset:
        """Parse provider records without performing network or file I/O."""
        raise NotImplementedError
