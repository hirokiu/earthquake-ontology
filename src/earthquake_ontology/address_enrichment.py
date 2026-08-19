"""Cached GSI reverse-geocoding for Japanese observation stations."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

import httpx

from .model import Station, StationAddress

GSI_REVERSE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
GSI_MUNICIPALITIES_URL = "https://maps.gsi.go.jp/js/muni.js"


@dataclass(frozen=True)
class EnrichmentSummary:
    total: int
    already_present: int
    enriched: int
    cache_hits: int
    not_found: int
    outside_japan: int


def _coordinate_key(latitude: Decimal, longitude: Decimal) -> str:
    return f"{latitude.quantize(Decimal('0.000001'))},{longitude.quantize(Decimal('0.000001'))}"


def _in_japan_bounds(station: Station) -> bool:
    return Decimal("20") <= station.latitude <= Decimal("46") and Decimal("122") <= station.longitude <= Decimal("154")


def parse_municipalities(javascript: str) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"GSI[.]MUNI_ARRAY\[[^]]+\]\s*=\s*'([^']+)'", javascript):
        parts = [part.replace("\u3000", "").strip() for part in match.group(1).split(",")]
        if len(parts) != 4:
            continue
        prefecture_code, prefecture, municipality_code, municipality = parts
        municipality_code = municipality_code.zfill(5)
        mapping[municipality_code] = {
            "prefecture_code": prefecture_code.zfill(2)[:2],
            "prefecture": prefecture,
            "municipality_code": municipality_code,
            "municipality": municipality,
        }
    return mapping


class GsiAddressEnricher:
    def __init__(
        self, cache_path: Path, client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep, interval_seconds: float = 0.2,
    ) -> None:
        self.cache_path = cache_path
        self._owns_client = client is None
        self.client = client or httpx.Client(
            headers={"User-Agent": "earthquake-ontology/0.1 (+https://seismic.balog.jp/)"},
            timeout=httpx.Timeout(30, connect=10), follow_redirects=True,
        )
        self.sleep = sleep
        if interval_seconds < 0:
            raise ValueError("address request interval must not be negative")
        self.interval_seconds = interval_seconds
        self.cache = self._load_cache()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def _load_cache(self) -> dict:
        if not self.cache_path.exists():
            return {"schema_version": 1, "municipalities": {}, "entries": {}}
        return json.loads(self.cache_path.read_text(encoding="utf-8"))

    def clear_cache(self) -> Path | None:
        """Reset all cached lookups, retaining a recoverable timestamped backup."""
        backup: Path | None = None
        if self.cache_path.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = self.cache_path.with_name(f"{self.cache_path.name}.backup-{timestamp}")
            os.replace(self.cache_path, backup)
        self.cache = {"schema_version": 1, "municipalities": {}, "entries": {}}
        self._save_cache()
        return backup

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_name(f".{self.cache_path.name}.tmp")
        try:
            temporary.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.cache_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _municipalities(self) -> dict[str, dict[str, str]]:
        mapping = self.cache.get("municipalities", {})
        if mapping:
            return mapping
        response = self.client.get(GSI_MUNICIPALITIES_URL)
        response.raise_for_status()
        mapping = parse_municipalities(response.text)
        if not mapping:
            raise ValueError("GSI municipality table contained no entries")
        self.cache["municipalities"] = mapping
        self.cache["municipalities_retrieved_at"] = datetime.now(timezone.utc).isoformat()
        self._save_cache()
        return mapping

    def enrich(self, stations: list[Station]) -> tuple[list[Station], EnrichmentSummary]:
        municipalities: dict[str, dict[str, str]] | None = None
        output: list[Station] = []
        already_present = enriched = cache_hits = not_found = outside_japan = 0
        for station in stations:
            if station.address is not None:
                already_present += 1
                output.append(station)
                continue
            if not _in_japan_bounds(station):
                outside_japan += 1
                output.append(station)
                continue
            key = _coordinate_key(station.latitude, station.longitude)
            cached = self.cache.setdefault("entries", {}).get(key)
            if cached is not None:
                cache_hits += 1
                entry = cached
            else:
                if municipalities is None:
                    municipalities = self._municipalities()
                response = self.client.get(
                    GSI_REVERSE_URL,
                    params={"lat": str(station.latitude), "lon": str(station.longitude)},
                )
                response.raise_for_status()
                municipality_code = str(response.json().get("results", {}).get("muniCd", "")).zfill(5)
                administrative = municipalities.get(municipality_code)
                entry = {
                    "status": "found" if administrative else "not_found",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "source_uri": str(response.request.url),
                    "administrative": administrative,
                }
                self.cache["entries"][key] = entry
                self._save_cache()
                if self.interval_seconds:
                    self.sleep(self.interval_seconds)
            administrative = entry.get("administrative")
            if not administrative:
                not_found += 1
                output.append(station)
                continue
            full_address = administrative["prefecture"] + administrative["municipality"]
            address = StationAddress(
                full_address=full_address,
                prefecture=administrative["prefecture"],
                prefecture_code=administrative["prefecture_code"],
                municipality=administrative["municipality"],
                municipality_code=administrative["municipality_code"],
            )
            output.append(replace(station, address=address))
            enriched += 1
        return output, EnrichmentSummary(
            len(stations), already_present, enriched, cache_hits, not_found, outside_japan,
        )
