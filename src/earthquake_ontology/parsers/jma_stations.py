"""Parser for JMA's intensity-observation station code list (code_p.zip)."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from ..model import ParseIssue, ParsedDataset, Station


JST = ZoneInfo("Asia/Tokyo")
RESOURCE_BASE = "https://seismic.balog.jp/resource/"


def _coordinate(value: str) -> Decimal:
    value = value.strip()
    if len(value) < 3 or not value.isdigit():
        raise ValueError(f"invalid degree-minute coordinate: {value!r}")
    degree_digits = len(value) - 2
    degrees = Decimal(value[:degree_digits])
    minutes = Decimal(value[degree_digits:])
    if minutes >= 60:
        raise ValueError(f"invalid coordinate minutes: {value!r}")
    return degrees + minutes / Decimal(60)


def _availability(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    year = value[:4]
    if len(year) != 4 or not year.isdigit():
        raise ValueError(f"invalid availability time: {value!r}")
    # Historical rows may contain 9 for unknown lower-precision components.
    if len(value) >= 12 and value[4:12].isdigit() and "9" not in value[4:12]:
        return datetime.strptime(value[:12], "%Y%m%d%H%M").replace(tzinfo=JST)
    return datetime(int(year), 1, 1, tzinfo=JST)


class JmaStationCodeParser:
    def __init__(self, source_uri: str) -> None:
        self.source_uri = source_uri

    def parse_zip(self, path: Path) -> ParsedDataset:
        result = ParsedDataset()
        with zipfile.ZipFile(path) as archive:
            members = []
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError(f"unsafe ZIP member: {info.filename}")
                if member.name.lower().endswith(".dat"):
                    members.append(info)
            if len(members) != 1:
                raise ValueError("JMA station ZIP must contain exactly one DAT file")
            with archive.open(members[0]) as binary:
                with io.TextIOWrapper(binary, encoding="euc_jp", newline="") as text:
                    self._parse_rows(text, result)
        return result

    def _parse_rows(self, text, result: ParsedDataset) -> None:
        for line, row in enumerate(csv.reader(text, delimiter="\t"), 1):
            try:
                if len(row) < 6:
                    raise ValueError("station row has fewer than six columns")
                identifier, label, latitude, longitude, start, end = row[:6]
                identifier = identifier.strip()
                if not identifier:
                    raise ValueError("station identifier is empty")
                result.stations.append(Station(
                    uri=f"{RESOURCE_BASE}sta-{identifier}",
                    identifier=identifier,
                    label_ja=label.strip().removesuffix("＊") or identifier,
                    latitude=_coordinate(latitude),
                    longitude=_coordinate(longitude),
                    network="JMA",
                    available_from=_availability(start),
                    available_until=_availability(end),
                    source_uri=self.source_uri,
                ))
            except (ValueError, InvalidOperation, TypeError) as exc:
                result.issues.append(ParseIssue(line, "invalid_jma_station", str(exc), repr(row)))
