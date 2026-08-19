"""Source-independent domain models used by every provider parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit


def _validate_uri(value: str, field_name: str) -> None:
    parsed = urlsplit(value)
    if not parsed.scheme or any(character.isspace() for character in value):
        raise ValueError(f"{field_name} must be an absolute URI without whitespace: {value!r}")


def _validate_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")


@dataclass(frozen=True)
class Hypocenter:
    uri: str
    origin_time: datetime
    latitude: Decimal
    longitude: Decimal
    source_uri: str
    label_ja: str | None = None
    label_en: str | None = None
    depth_m: Decimal | None = None
    magnitude: Decimal | None = None
    magnitude_type: str | None = None
    catalog: str | None = None
    determination_method: str | None = None
    determined_by_uri: str | None = None
    record_type: str | None = None
    maximum_intensity: str | None = None
    observed_station_count: int | None = None
    travel_time_table: str | None = None

    def __post_init__(self) -> None:
        _validate_uri(self.uri, "uri")
        _validate_uri(self.source_uri, "source_uri")
        _validate_datetime(self.origin_time, "origin_time")
        if self.determined_by_uri is not None:
            _validate_uri(self.determined_by_uri, "determined_by_uri")
        if not Decimal("-90") <= self.latitude <= Decimal("90"):
            raise ValueError("latitude must be between -90 and 90")
        if not Decimal("-180") <= self.longitude <= Decimal("180"):
            raise ValueError("longitude must be between -180 and 180")
        if self.observed_station_count is not None and self.observed_station_count < 0:
            raise ValueError("observed_station_count must not be negative")


@dataclass(frozen=True)
class Observation:
    uri: str
    start_time: datetime
    hypocenter_uri: str
    station_uri: str
    source_uri: str
    intensity: str | None = None
    calculated_intensity: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("uri", "hypocenter_uri", "station_uri", "source_uri"):
            _validate_uri(getattr(self, name), name)
        _validate_datetime(self.start_time, "start_time")


@dataclass(frozen=True)
class StationAddress:
    full_address: str
    address_uri: str | None = None
    prefecture: str | None = None
    prefecture_code: str | None = None
    municipality: str | None = None
    municipality_code: str | None = None
    country: str | None = None
    language: str = "ja"

    def __post_init__(self) -> None:
        if not self.full_address.strip():
            raise ValueError("full_address must not be empty")
        if self.address_uri is not None:
            _validate_uri(self.address_uri, "address_uri")


@dataclass(frozen=True)
class Station:
    uri: str
    identifier: str
    latitude: Decimal
    longitude: Decimal
    source_uri: str
    label_ja: str | None = None
    label_en: str | None = None
    elevation_m: Decimal | None = None
    network: str | None = None
    available_from: datetime | None = None
    available_until: datetime | None = None
    address: StationAddress | None = None
    region: str | None = None
    additional_source_uris: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_uri(self.uri, "uri")
        _validate_uri(self.source_uri, "source_uri")
        for source_uri in self.additional_source_uris:
            _validate_uri(source_uri, "additional_source_uris")
        if not self.identifier.strip():
            raise ValueError("identifier must not be empty")
        if not Decimal("-90") <= self.latitude <= Decimal("90"):
            raise ValueError("latitude must be between -90 and 90")
        if not Decimal("-180") <= self.longitude <= Decimal("180"):
            raise ValueError("longitude must be between -180 and 180")
        for name in ("available_from", "available_until"):
            value = getattr(self, name)
            if value is not None:
                _validate_datetime(value, name)


@dataclass(frozen=True)
class StrongMotionRecord:
    uri: str
    identifier: str
    station_uri: str
    hypocenter_uri: str
    source_uri: str
    file_basename: str | None = None
    sample_count: int | None = None
    sampling_frequency_hz: Decimal | None = None
    pga_ns: Decimal | None = None
    pga_ew: Decimal | None = None
    pga_ud: Decimal | None = None
    pgv_ns: Decimal | None = None
    pgv_ew: Decimal | None = None
    pgv_ud: Decimal | None = None
    spectrum_intensity: Decimal | None = None
    instrumental_intensity: Decimal | None = None
    fault_distance_km: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("uri", "station_uri", "hypocenter_uri", "source_uri"):
            _validate_uri(getattr(self, name), name)
        if not self.identifier.strip():
            raise ValueError("identifier must not be empty")
        if self.sample_count is not None and self.sample_count < 0:
            raise ValueError("sample_count must not be negative")
        if self.sampling_frequency_hz is not None and self.sampling_frequency_hz <= 0:
            raise ValueError("sampling_frequency_hz must be positive")


@dataclass(frozen=True)
class DatasetSnapshot:
    uri: str
    dataset_uri: str
    source_uri: str
    generated_at: datetime
    source_sha256: str
    graph_uri: str
    previous_snapshot_uri: str | None = None
    converter_version: str | None = None

    def __post_init__(self) -> None:
        for name in ("uri", "dataset_uri", "source_uri", "graph_uri"):
            _validate_uri(getattr(self, name), name)
        if self.previous_snapshot_uri is not None:
            _validate_uri(self.previous_snapshot_uri, "previous_snapshot_uri")
        _validate_datetime(self.generated_at, "generated_at")
        if len(self.source_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in self.source_sha256):
            raise ValueError("source_sha256 must be a 64-character hexadecimal SHA-256 digest")


@dataclass
class ParsedDataset:
    hypocenters: list[Hypocenter] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    stations: list[Station] = field(default_factory=list)
    strong_motion_records: list[StrongMotionRecord] = field(default_factory=list)
    issues: list["ParseIssue"] = field(default_factory=list)


@dataclass(frozen=True)
class ParseIssue:
    line: int
    code: str
    message: str
    raw_record: str
