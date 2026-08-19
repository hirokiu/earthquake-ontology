"""Parser for JMA's provisional daily hypocenter HTML pages."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import quote

from ..model import Hypocenter, ParseIssue, ParsedDataset

JST = timezone(timedelta(hours=9))
ROW = re.compile(
    r"^\s*(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2}):(\d{2})\s+"
    r"([\d.]+)\s+(\d+)°\s*([\d.]+)'[NS]\s+(\d+)°\s*([\d.]+)'[EW]\s+"
    r"([\d.]+)\s+([\d.-]+)\s+(.+?)\s*$"
)


class _PreText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_pre = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, _attrs):
        if tag.lower() == "pre":
            self.in_pre = True

    def handle_endtag(self, tag):
        if tag.lower() == "pre":
            self.in_pre = False

    def handle_data(self, data):
        if self.in_pre:
            self.parts.append(data)


class JmaDailyHypocenterParser:
    def __init__(self, source_uri: str, resource_base: str = "https://seismic.balog.jp/resource/jma/daily/") -> None:
        self.source_uri = source_uri
        self.resource_base = resource_base.rstrip("/") + "/"

    def parse_html(self, html: str) -> ParsedDataset:
        extractor = _PreText()
        extractor.feed(html)
        result = ParsedDataset()
        for line_number, raw in enumerate("".join(extractor.parts).splitlines(), 1):
            match = ROW.match(raw)
            if not match:
                continue
            try:
                year, month, day, hour, minute = map(int, match.groups()[:5])
                second = Decimal(match.group(6))
                base = datetime(year, month, day, hour, minute, tzinfo=JST)
                origin = base + timedelta(seconds=float(second))
                lat = Decimal(match.group(7)) + Decimal(match.group(8)) / 60
                lon = Decimal(match.group(9)) + Decimal(match.group(10)) / 60
                depth = Decimal(match.group(11)) * 1000
                magnitude_text = match.group(12)
                magnitude = None if magnitude_text in {"-", "--"} else Decimal(magnitude_text)
                region = match.group(13).strip()
                record_id = origin.strftime("%Y%m%d%H%M%S") + f"-{line_number}"
                result.hypocenters.append(Hypocenter(
                    uri=self.resource_base + quote(record_id), origin_time=origin,
                    latitude=lat, longitude=lon, depth_m=depth, magnitude=magnitude,
                    magnitude_type="Mj", label_ja=region, catalog="JMA daily provisional",
                    determined_by_uri="https://www.jma.go.jp/jma/",
                    source_uri=self.source_uri,
                ))
            except (ValueError, ArithmeticError) as exc:
                result.issues.append(ParseIssue(line_number, "invalid_daily_row", str(exc), raw))
        if not result.hypocenters:
            result.issues.append(ParseIssue(0, "no_records", "no daily hypocenter rows found", ""))
        return result
