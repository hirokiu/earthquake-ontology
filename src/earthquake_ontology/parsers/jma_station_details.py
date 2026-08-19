"""Merge JMA's human-readable intensity-station table into code_p stations."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from ..model import Station, StationAddress


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data):
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.in_cell:
            self.row.append("".join(self.cell_parts).strip())
            self.in_cell = False
        elif tag == "tr":
            if len(self.row) == 9 and self.row[0] != "地域名称":
                self.rows.append(self.row)
            self.row = []


def merge_jma_station_details(
    stations: list[Station], html_path: Path, details_source_uri: str,
) -> list[Station]:
    parser = _TableParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    by_label: dict[str, list[tuple[list[str], Decimal, Decimal]]] = {}
    for row in parser.rows:
        try:
            latitude = Decimal(row[3]) + Decimal(row[4]) / Decimal(60)
            longitude = Decimal(row[5]) + Decimal(row[6]) / Decimal(60)
        except Exception:
            continue
        by_label.setdefault(row[1].rstrip("＊"), []).append((row, latitude, longitude))

    merged = []
    for station in stations:
        candidates = by_label.get((station.label_ja or "").rstrip("＊"), [])
        if not candidates:
            merged.append(station)
            continue
        row, latitude, longitude = min(
            candidates,
            key=lambda item: abs(item[1] - station.latitude) + abs(item[2] - station.longitude),
        )
        if abs(latitude - station.latitude) + abs(longitude - station.longitude) > Decimal("0.1"):
            merged.append(station)
            continue
        merged.append(replace(
            station,
            address=StationAddress(full_address=row[2]),
            region=row[0],
            additional_source_uris=station.additional_source_uris + (details_source_uri,),
        ))
    return merged
