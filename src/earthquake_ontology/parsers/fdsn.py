"""Dependency-free parsers for FDSN QuakeML and StationXML responses."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from ..model import Hypocenter, ParseIssue, ParsedDataset, Station, StationAddress
from .base import agency_uri


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element, name: str):
    return [child for child in element if _local(child.tag) == name]


def _child(element, name: str):
    return next((child for child in element if _local(child.tag) == name), None)


def _text(element, path: str) -> str | None:
    current = element
    for name in path.split("/"):
        current = _child(current, name) if current is not None else None
    if current is None or current.text is None:
        return None
    return current.text.strip()


def _decimal(element, path: str) -> Decimal | None:
    value = _text(element, path)
    return Decimal(value) if value not in {None, ""} else None


def _instant(value: str | None) -> datetime:
    if not value:
        raise ValueError("missing date-time")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _event_uri(public_id: str) -> str:
    # Retain the URI shape used by the repository's historical IRIS exports.
    if public_id.startswith("smi:service.iris.edu/"):
        return "http://service.iris.edu/" + public_id.removeprefix("smi:service.iris.edu/")
    if public_id.startswith("smi://service.iris.edu/"):
        return "http://service.iris.edu/" + public_id.removeprefix("smi://service.iris.edu/")
    if public_id.startswith("quakeml:"):
        return "https://" + public_id.removeprefix("quakeml:")
    if public_id.startswith(("http://", "https://")):
        return public_id
    return "https://seismic.balog.jp/resource/fdsn/event/" + quote(public_id, safe="")


def _safe_root_from_bytes(value: bytes):
    header = value[:65536].upper()
    if b"<!DOCTYPE" in header or b"<!ENTITY" in header:
        raise ValueError("DTD and entity declarations are not accepted")
    return ET.fromstring(value)


def _safe_root_from_file(path: Path):
    with path.open("rb") as source:
        header = source.read(65536).upper()
    if b"<!DOCTYPE" in header or b"<!ENTITY" in header:
        raise ValueError("DTD and entity declarations are not accepted")
    return ET.parse(path).getroot()


class FdsnQuakeMlParser:
    def __init__(self, source_uri: str) -> None:
        self.source_uri = source_uri

    def parse_file(self, path: Path) -> ParsedDataset:
        return self.parse_root(_safe_root_from_file(path))

    def parse_bytes(self, value: bytes) -> ParsedDataset:
        return self.parse_root(_safe_root_from_bytes(value))

    def parse_root(self, root) -> ParsedDataset:
        result = ParsedDataset()
        events = [element for element in root.iter() if _local(element.tag) == "event"]
        for number, event in enumerate(events, 1):
            try:
                origins = _children(event, "origin")
                magnitudes = _children(event, "magnitude")
                preferred_origin = _text(event, "preferredOriginID")
                preferred_magnitude = _text(event, "preferredMagnitudeID")
                origin = next((item for item in origins if item.get("publicID") == preferred_origin), origins[0] if origins else None)
                magnitude = next((item for item in magnitudes if item.get("publicID") == preferred_magnitude), magnitudes[0] if magnitudes else None)
                if origin is None:
                    raise ValueError("event has no origin")
                public_id = event.get("publicID") or origin.get("publicID") or f"event-{number}"
                descriptions = _children(event, "description")
                label = next((_text(item, "text") for item in descriptions if _text(item, "text")), None)
                catalog = _text(origin, "creationInfo/agencyID") or _text(origin, "creationInfo/author")
                origin_agency = _text(origin, "creationInfo/agencyID") or _text(origin, "creationInfo/author")
                determination_method = _text(origin, "evaluationMode") or _text(origin, "methodID")
                depth = _decimal(origin, "depth/value")
                result.hypocenters.append(Hypocenter(
                    uri=_event_uri(public_id), origin_time=_instant(_text(origin, "time/value")),
                    latitude=_decimal(origin, "latitude/value"), longitude=_decimal(origin, "longitude/value"),
                    depth_m=depth, magnitude=_decimal(magnitude, "mag/value") if magnitude is not None else None,
                    magnitude_type=_text(magnitude, "type") if magnitude is not None else None,
                    label_en=label, catalog=catalog, determination_method=determination_method,
                    determined_by_uri=agency_uri(origin_agency),
                    source_uri=self.source_uri,
                ))
            except (ValueError, InvalidOperation, TypeError) as exc:
                result.issues.append(ParseIssue(number, "invalid_fdsn_event", str(exc), event.get("publicID", "")))
        if not events:
            result.issues.append(ParseIssue(0, "no_events", "QuakeML contains no events", ""))
        return result


class FdsnStationXmlParser:
    def __init__(self, source_uri: str) -> None:
        self.source_uri = source_uri

    def parse_file(self, path: Path) -> ParsedDataset:
        return self.parse_root(_safe_root_from_file(path))

    def parse_bytes(self, value: bytes) -> ParsedDataset:
        return self.parse_root(_safe_root_from_bytes(value))

    def parse_root(self, root) -> ParsedDataset:
        result = ParsedDataset()
        for network in (item for item in root.iter() if _local(item.tag) == "Network"):
            network_code = (network.get("code") or "").strip()
            for number, station in enumerate(_children(network, "Station"), 1):
                try:
                    station_code = (station.get("code") or "").strip()
                    identifier = f"{network_code}.{station_code}"
                    site = _child(station, "Site")
                    address = self._site_address(site)
                    result.stations.append(Station(
                        uri="https://seismic.balog.jp/resource/sta-FDSN-" + quote(identifier),
                        identifier=identifier, network=network_code,
                        label_en=_text(site, "Name") if site is not None else identifier,
                        latitude=_decimal(station, "Latitude"), longitude=_decimal(station, "Longitude"),
                        elevation_m=_decimal(station, "Elevation"),
                        available_from=_instant(station.get("startDate")) if station.get("startDate") else None,
                        available_until=_instant(station.get("endDate")) if station.get("endDate") else None,
                        address=address,
                        source_uri=self.source_uri,
                    ))
                except (ValueError, InvalidOperation, TypeError) as exc:
                    result.issues.append(ParseIssue(number, "invalid_fdsn_station", str(exc), identifier))
        if not result.stations:
            result.issues.append(ParseIssue(0, "no_stations", "StationXML contains no stations", ""))
        return result

    @staticmethod
    def _site_address(site) -> StationAddress | None:
        if site is None:
            return None
        country = _text(site, "Country")
        region = _text(site, "Region")
        county = _text(site, "County")
        town = _text(site, "Town")
        components = [value for value in (country, region, county, town) if value]
        if not components:
            return None
        is_japanese = (country or "").upper() in {"JP", "JPN", "JAPAN", "日本"}
        full_address = "".join(components[1:] if is_japanese else components)
        if not is_japanese:
            full_address = ", ".join(reversed(components))
        return StationAddress(
            full_address=full_address, prefecture=region if is_japanese else None,
            municipality=town or county if is_japanese else None,
            country=country, language="ja" if is_japanese else "en",
        )
