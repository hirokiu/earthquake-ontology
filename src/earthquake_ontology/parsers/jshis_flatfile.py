"""Safe, schema-name based reader for the J-SHIS ground-motion flat file."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from ..model import Hypocenter, ParseIssue, ParsedDataset, Station, StrongMotionRecord

JST = timezone(timedelta(hours=9))
BASE = "https://seismic.balog.jp/resource/jshis/"


def _decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    if not value or value in {"-", "NA", "N/A", "null"}:
        return None
    return Decimal(value)


def _integer(value: str | None) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None else None


def _date(value: str | None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=JST)
        except ValueError:
            pass
    raise ValueError(f"unsupported date: {value}")


def _datetime(value: str | None) -> datetime:
    value = (value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=JST)
        except ValueError:
            pass
    raise ValueError(f"unsupported origin time: {value}")


class JshisFlatFileParser:
    REQUIRED = {"site_schema.tsv", "source_schema.tsv", "smrec_schema.tsv"}

    def __init__(self, source_uri: str) -> None:
        self.source_uri = source_uri

    def parse_zip(self, path: Path) -> ParsedDataset:
        result = ParsedDataset()
        with zipfile.ZipFile(path) as archive:
            members: dict[str, zipfile.ZipInfo] = {}
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError(f"unsafe ZIP member: {info.filename}")
                if member.name in self.REQUIRED:
                    members[member.name] = info
            missing = self.REQUIRED - members.keys()
            if missing:
                raise ValueError(f"flat file is missing: {', '.join(sorted(missing))}")
            for name, handler in (("site_schema.tsv", self._sites), ("source_schema.tsv", self._sources), ("smrec_schema.tsv", self._records)):
                with archive.open(members[name]) as binary:
                    with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                        handler(text, result)
        return result

    def _rows(self, text):
        return csv.DictReader(text, delimiter="\t")

    def _sites(self, text, result: ParsedDataset) -> None:
        networks = {"1": "K-NET", "2": "KiK-net"}
        for line, row in enumerate(self._rows(text), 2):
            try:
                identifier = (row.get("siteid2") or row.get("site_code") or "").strip()
                result.stations.append(Station(
                    uri=BASE + "station/" + quote(identifier), identifier=identifier,
                    label_ja=(row.get("site_name") or "").strip() or None,
                    latitude=_decimal(row.get("lat")), longitude=_decimal(row.get("lon")),
                    elevation_m=_decimal(row.get("elevation")),
                    network=networks.get((row.get("obs_network_id") or "").strip(), row.get("obs_network_id")),
                    available_from=_date(row.get("start_date")), available_until=_date(row.get("end_date")),
                    source_uri=self.source_uri,
                ))
            except (ValueError, InvalidOperation, TypeError) as exc:
                result.issues.append(ParseIssue(line, "invalid_site", str(exc), repr(row)))

    def _sources(self, text, result: ParsedDataset) -> None:
        for line, row in enumerate(self._rows(text), 2):
            try:
                identifier = (row.get("eq_source_id") or "").strip()
                result.hypocenters.append(Hypocenter(
                    uri=BASE + "source/" + quote(identifier), origin_time=_datetime(row.get("jem_origin_time")),
                    latitude=_decimal(row.get("jem_lat")), longitude=_decimal(row.get("jem_lon")),
                    depth_m=(_decimal(row.get("jem_depth")) or Decimal(0)) * 1000,
                    magnitude=_decimal(row.get("mjma")), magnitude_type="Mj",
                    label_ja=(row.get("eq_event_name") or "").strip() or None,
                    catalog="J-SHIS ground-motion flat file", source_uri=self.source_uri,
                ))
            except (ValueError, InvalidOperation, TypeError) as exc:
                result.issues.append(ParseIssue(line, "invalid_source", str(exc), repr(row)))

    def _records(self, text, result: ParsedDataset) -> None:
        for line, row in enumerate(self._rows(text), 2):
            try:
                identifier = (row.get("smrec_id") or "").strip()
                site_id = (row.get("site_id") or "").strip()
                source_id = (row.get("eq_source_id") or "").strip()
                result.strong_motion_records.append(StrongMotionRecord(
                    uri=BASE + "record/" + quote(identifier), identifier=identifier,
                    station_uri=BASE + "station/" + quote(site_id),
                    hypocenter_uri=BASE + "source/" + quote(source_id), source_uri=self.source_uri,
                    file_basename=(row.get("filebasename") or "").strip() or None,
                    sample_count=_integer(row.get("length")), sampling_frequency_hz=_decimal(row.get("samplefreq")),
                    pga_ns=_decimal(row.get("maxacc0")), pga_ew=_decimal(row.get("maxacc1")), pga_ud=_decimal(row.get("maxacc2")),
                    pgv_ns=_decimal(row.get("maxvel0")), pgv_ew=_decimal(row.get("maxvel1")), pgv_ud=_decimal(row.get("maxvel2")),
                    spectrum_intensity=_decimal(row.get("sival")), instrumental_intensity=_decimal(row.get("sindo")),
                    fault_distance_km=_decimal(row.get("fault_dist")),
                ))
            except (ValueError, InvalidOperation, TypeError) as exc:
                result.issues.append(ParseIssue(line, "invalid_smrec", str(exc), repr(row)))
