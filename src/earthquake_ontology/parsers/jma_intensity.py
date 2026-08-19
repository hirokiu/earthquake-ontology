"""Parser for JMA monthly hypocenter/intensity fixed-width records."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable
from zoneinfo import ZoneInfo

from earthquake_ontology.model import Hypocenter, Observation, ParsedDataset, ParseIssue
from earthquake_ontology.parsers.base import DatasetParser


JST = ZoneInfo("Asia/Tokyo")
RESOURCE_BASE = "https://seismic.balog.jp/resource/"

HYPO_WIDTHS = (1, 4, 2, 2, 2, 2, 4, 4, 3, 4, 4, 4, 4, 4, 5, 3, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 3, 28)
OBS_WIDTHS = (7, 1, 2, 2, 2, 3, 1, 1, 1, 2, 1, 2, 3, 1, 5, 1, 1, 5, 1, 1, 5, 1, 1, 5, 1, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 1, 3, 10, 1, 5)

RECORD_TYPES = {
    "A": "震源レコード", "B": "群発地震時の震源レコード", "D": "震源が離れた地震の組の震源レコード",
}
DETERMINATION_METHODS = {
    "K": "気象庁震源", "S": "気象庁参考震源", "k": "簡易気象庁震源", "s": "簡易参考震源",
    "A": "自動気象庁震源", "a": "自動参考震源", "N": "震源固定・震源不定・未計算",
    "F": "遠地", "U": "USGS震源", "I": "ISC震源", "H": "震度観測時刻が時間単位までのデータ",
    "D": "震度観測時刻が日単位までのデータ", "M": "震度観測時刻が月単位までのデータ",
}
INTENSITIES = {
    "1": "震度1", "2": "震度2", "3": "震度3", "4": "震度4",
    "5": "震度5(1996年9月まで)", "6": "震度6(1996年9月まで)", "7": "震度7",
    "A": "震度5弱", "B": "震度5強", "C": "震度6弱", "D": "震度6強",
    "L": "局発地震", "S": "小局発地震", "M": "やや顕著地震", "R": "顕著地震",
    "F": "有感地震", "X": "付近有感",
}
TRAVEL_TIME_TABLES = (
    "他機関", "標準走時表(83Aなど)", "三陸沖用走時表", "北海道東方沖用走時表",
    "千島列島付近用走時表(1を併用)", "標準走時表(JMA2001)", "千島列島付近用走時表(5を併用)",
)


class JmaRecordError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _split(line: str, widths: tuple[int, ...]) -> list[str]:
    values: list[str] = []
    position = 0
    for width in widths:
        values.append(line[position:position + width])
        position += width
    return values


def _decimal(raw: str) -> Decimal | None:
    value = raw.strip()
    if not value or "/" in value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise JmaRecordError("INVALID_NUMBER", f"invalid numeric field: {raw!r}") from exc


def _jma_datetime(parts: list[str]) -> datetime:
    second = parts[6]
    required = parts[1:6] + [second[:2]]
    if any(not value.strip().isdigit() for value in required):
        raise JmaRecordError("INCOMPLETE_ORIGIN_TIME", "origin time is incomplete")
    hundredths = int(second[2:4]) if second[2:4].strip().isdigit() else 0
    return datetime(
        int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5]), int(second[:2]),
        hundredths * 10_000, tzinfo=JST,
    )


def _coordinate(degrees_raw: str, minutes_raw: str, fixed: bool) -> Decimal:
    degrees = _decimal(degrees_raw)
    minutes = _decimal(minutes_raw)
    if degrees is None or minutes is None:
        raise JmaRecordError("MISSING_COORDINATE", "latitude or longitude is incomplete")
    if not fixed:
        minutes /= Decimal(100)
    return degrees + minutes / Decimal(60)


def _magnitude(integer_raw: str, decimal_raw: str) -> Decimal | None:
    integer_code = integer_raw.strip()
    fraction = _decimal(decimal_raw)
    if not integer_code or fraction is None:
        return None
    negative_codes = {"-": Decimal("0"), "A": Decimal("-1"), "B": Decimal("-2"), "C": Decimal("-3")}
    if integer_code in negative_codes:
        return negative_codes[integer_code] - fraction / Decimal(10)
    try:
        return Decimal(integer_code) + fraction / Decimal(10)
    except InvalidOperation as exc:
        raise JmaRecordError("INVALID_MAGNITUDE", f"invalid magnitude: {integer_raw!r}{decimal_raw!r}") from exc


def _observation_datetime(origin: datetime, parts: list[str]) -> datetime:
    values = [part.strip() for part in (parts[2], parts[3], parts[4], parts[5][:2])]
    if any(not value.isdigit() for value in values):
        raise JmaRecordError("INCOMPLETE_OBSERVATION_TIME", "observation time is incomplete")
    day, hour, minute, second = map(int, values)
    year, month = origin.year, origin.month
    if day < origin.day - 20:
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    if day > monthrange(year, month)[1]:
        raise JmaRecordError("INVALID_OBSERVATION_TIME", "observation day is outside the month")
    hundredths = int(parts[5][2]) if parts[5][2:3].isdigit() else 0
    return datetime(year, month, day, hour, minute, second, hundredths * 100_000, tzinfo=JST)


class JmaIntensityParser(DatasetParser):
    def __init__(self, source_uri: str, resource_base: str = RESOURCE_BASE):
        self.source_uri = source_uri
        self.resource_base = resource_base.rstrip("/") + "/"

    def parse_lines(self, lines: Iterable[str]) -> ParsedDataset:
        result = ParsedDataset()
        current: Hypocenter | None = None
        for number, raw_line in enumerate(lines, 1):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            try:
                if line[0] in RECORD_TYPES:
                    current = self._parse_hypocenter(line)
                    result.hypocenters.append(current)
                elif current is None:
                    raise JmaRecordError("ORPHAN_OBSERVATION", "observation appears before a hypocenter")
                else:
                    result.observations.append(self._parse_observation(line, current))
            except (JmaRecordError, ValueError) as exc:
                code = exc.code if isinstance(exc, JmaRecordError) else "INVALID_RECORD"
                result.issues.append(ParseIssue(number, code, str(exc), line))
        return result

    def _parse_hypocenter(self, line: str) -> Hypocenter:
        parts = _split(line, HYPO_WIDTHS)
        event_id = line[:17].strip()
        if not event_id:
            raise JmaRecordError("MISSING_EVENT_ID", "hypocenter identifier is empty")
        origin = _jma_datetime(parts)
        judge = parts[22].strip()
        fixed = judge == "9"
        latitude = _coordinate(parts[8], parts[9], fixed)
        longitude = _coordinate(parts[11], parts[12], fixed)
        depth = _decimal(parts[14])
        if depth is not None:
            depth_km = depth / Decimal(100) if judge in {"1", "M"} else depth
            depth = depth_km * Decimal(1000)
        locale = parts[29]
        label = locale[:-8].strip() or None
        station_count_raw = locale[-8:-3].strip()
        determination_code = locale[-3:-2]
        travel_raw = parts[21].strip()
        travel_index = int(travel_raw) if travel_raw.isdigit() else 0
        travel_table = TRAVEL_TIME_TABLES[travel_index - 1] if 1 <= travel_index <= len(TRAVEL_TIME_TABLES) else TRAVEL_TIME_TABLES[0]
        return Hypocenter(
            uri=self.resource_base + event_id,
            origin_time=origin,
            latitude=latitude,
            longitude=longitude,
            source_uri=self.source_uri,
            label_ja=label,
            depth_m=depth,
            magnitude=_magnitude(parts[16], parts[17]),
            magnitude_type=parts[18].strip() or None,
            determination_method=DETERMINATION_METHODS.get(determination_code, determination_code or None),
            record_type=RECORD_TYPES.get(parts[0]),
            maximum_intensity=INTENSITIES.get(parts[24].strip(), parts[24].strip() or None),
            observed_station_count=int(station_count_raw) if station_count_raw.isdigit() else None,
            travel_time_table=travel_table,
        )

    def _parse_observation(self, line: str, hypocenter: Hypocenter) -> Observation:
        parts = _split(line, OBS_WIDTHS)
        station_id = parts[0].strip()
        if not station_id:
            raise JmaRecordError("MISSING_STATION_ID", "station identifier is empty")
        event_id = hypocenter.uri.rsplit("/", 1)[-1]
        calculated_raw = parts[9].strip()
        calculated = Decimal(calculated_raw) / Decimal(10) if calculated_raw.isdigit() else None
        intensity_code = parts[7].strip()
        return Observation(
            uri=f"{self.resource_base}{station_id}-{event_id}",
            start_time=_observation_datetime(hypocenter.origin_time, parts),
            hypocenter_uri=hypocenter.uri,
            station_uri=f"{self.resource_base}sta-{station_id}",
            source_uri=self.source_uri,
            intensity=INTENSITIES.get(intensity_code, intensity_code or None),
            calculated_intensity=calculated,
        )
