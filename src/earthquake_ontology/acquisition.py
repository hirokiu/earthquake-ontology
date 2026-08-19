"""Discover and immutably archive authoritative provider artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlencode, urljoin, urlsplit

import httpx

from .config import AppSettings, BasicAuthConfig, DirectDiscovery, FdsnYearlyDiscovery, HtmlLinksDiscovery, SourceConfig


@dataclass(frozen=True)
class RemoteArtifact:
    source_id: str
    period: str
    url: str
    destination_name: str


@dataclass(frozen=True)
class FetchResult:
    artifact: RemoteArtifact
    status: str
    path: str | None
    sha256: str | None
    retrieved_at: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


def _auth(config: BasicAuthConfig | None) -> httpx.BasicAuth | None:
    if config is None:
        return None
    username = os.environ.get(config.username_env)
    password = os.environ.get(config.password_env)
    if not username or not password:
        raise ValueError(
            f"basic authentication requires {config.username_env} and {config.password_env}"
        )
    return httpx.BasicAuth(username, password)


class DataFetcher:
    def __init__(
        self,
        settings: AppSettings,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.Client(
            headers={"User-Agent": settings.http.user_agent},
            timeout=httpx.Timeout(
                settings.http.read_timeout_seconds,
                connect=settings.http.connect_timeout_seconds,
            ),
            follow_redirects=True,
            transport=httpx.HTTPTransport(retries=settings.http.retries),
        )
        self.sleep = sleep

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "DataFetcher":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _request(self, url: str, *, headers: dict[str, str] | None = None, auth=None) -> httpx.Response:
        attempts = self.settings.http.retries + 1
        response: httpx.Response | None = None
        for attempt in range(attempts):
            response = self.client.get(url, headers=headers, auth=auth)
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt + 1 < attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 30)
                self.sleep(delay)
        assert response is not None
        return response

    def discover(self, source_id: str, source: SourceConfig) -> list[RemoteArtifact]:
        discovery = source.discovery
        if isinstance(discovery, DirectDiscovery):
            return [RemoteArtifact(source_id, discovery.period, str(discovery.url), source.destination_name.format(period=discovery.period))]
        if isinstance(discovery, HtmlLinksDiscovery):
            response = self._request(str(discovery.index_url), auth=_auth(source.auth))
            response.raise_for_status()
            parser = _LinkParser()
            parser.feed(response.text)
            pattern = re.compile(discovery.link_pattern)
            artifacts: dict[str, RemoteArtifact] = {}
            for href in parser.links:
                url = urljoin(str(discovery.index_url), href)
                match = pattern.search(urlsplit(url).path)
                if not match:
                    continue
                period = match.group("period")
                artifacts[period] = RemoteArtifact(
                    source_id, period, url, source.destination_name.format(period=period)
                )
            return [artifacts[key] for key in sorted(artifacts)]
        if isinstance(discovery, FdsnYearlyDiscovery):
            current_year = datetime.now(timezone.utc).year
            end_year = current_year if discovery.end_year == "current" else discovery.end_year
            artifacts = []
            for year in range(discovery.start_year, end_year + 1):
                query = {
                    "starttime": f"{year:04d}-01-01T00:00:00Z",
                    "endtime": f"{year + 1:04d}-01-01T00:00:00Z",
                    "format": "xml",
                    "orderby": "time-asc",
                    "nodata": "404",
                }
                if discovery.minimum_magnitude is not None:
                    query["minmagnitude"] = str(discovery.minimum_magnitude)
                if discovery.catalog:
                    query["catalog"] = discovery.catalog
                url = f"{str(discovery.endpoint).rstrip('/')}?{urlencode(query)}"
                period = str(year)
                artifacts.append(RemoteArtifact(
                    source_id, period, url, source.destination_name.format(period=period)
                ))
            return artifacts
        raise TypeError(f"unsupported discovery configuration: {type(discovery).__name__}")

    def fetch(
        self,
        artifact: RemoteArtifact,
        source: SourceConfig,
        *,
        force: bool = False,
    ) -> FetchResult:
        manifest_path = self.settings.storage.manifest_directory / f"{artifact.source_id}.json"
        manifest = self._load_manifest(manifest_path)
        previous = manifest.get("artifacts", {}).get(artifact.url, {})
        headers: dict[str, str] = {}
        if not force:
            if previous.get("etag"):
                headers["If-None-Match"] = previous["etag"]
            if previous.get("last_modified"):
                headers["If-Modified-Since"] = previous["last_modified"]

        retrieved_at = datetime.now(timezone.utc).isoformat()
        period_root = self.settings.storage.raw_directory / artifact.source_id / artifact.period
        period_root.mkdir(parents=True, exist_ok=True)
        status_code, response_headers, temporary_path, digest, byte_count = self._stream_to_temporary(
            artifact.url, period_root, headers=headers, auth=_auth(source.auth)
        )
        if status_code == 304:
            return FetchResult(artifact, "not_modified", previous.get("path"), previous.get("sha256"), retrieved_at)
        assert temporary_path is not None and digest is not None
        destination = (
            period_root
            / digest
            / artifact.destination_name
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        is_new = not destination.exists()
        if is_new:
            os.replace(temporary_path, destination)
        elif temporary_path.exists():
            temporary_path.unlink()

        metadata = {
            "source_id": artifact.source_id,
            "period": artifact.period,
            "url": artifact.url,
            "dataset_uri": str(source.dataset_uri),
            "license_url": str(source.license_url) if source.license_url else None,
            "retrieved_at": retrieved_at,
            "sha256": digest,
            "bytes": byte_count,
            "media_type": response_headers.get("Content-Type", source.media_type).split(";", 1)[0],
            "etag": response_headers.get("ETag"),
            "last_modified": response_headers.get("Last-Modified"),
            "path": str(destination),
        }
        sidecar = destination.with_suffix(destination.suffix + ".metadata.json")
        if not sidecar.exists():
            sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest.setdefault("artifacts", {})[artifact.url] = metadata
        self._write_manifest(manifest_path, manifest)
        return FetchResult(artifact, "downloaded" if is_new else "unchanged_content", str(destination), digest, retrieved_at)

    def _stream_to_temporary(
        self,
        url: str,
        directory: Path,
        *,
        headers: dict[str, str],
        auth,
    ) -> tuple[int, httpx.Headers, Path | None, str | None, int]:
        attempts = self.settings.http.retries + 1
        for attempt in range(attempts):
            with self.client.stream("GET", url, headers=headers, auth=auth) as response:
                if response.status_code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 30)
                    self.sleep(delay)
                    continue
                if response.status_code == 304:
                    return 304, response.headers, None, None, 0
                response.raise_for_status()
                digest = hashlib.sha256()
                byte_count = 0
                handle = tempfile.NamedTemporaryFile(prefix=".download-", suffix=".tmp", dir=directory, delete=False)
                temporary = Path(handle.name)
                try:
                    with handle:
                        for chunk in response.iter_bytes():
                            handle.write(chunk)
                            digest.update(chunk)
                            byte_count += len(chunk)
                    return response.status_code, response.headers, temporary, digest.hexdigest(), byte_count
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
        raise RuntimeError("download retry loop exhausted")

    def fetch_sources(
        self,
        source_ids: Iterable[str] | None = None,
        periods: set[str] | None = None,
        *,
        force: bool = False,
    ) -> list[FetchResult]:
        selected = set(source_ids) if source_ids else None
        if selected:
            missing = selected - set(self.settings.sources)
            if missing:
                raise KeyError(f"unknown source IDs: {', '.join(sorted(missing))}")
        results: list[FetchResult] = []
        for source_id, source in self.settings.sources.items():
            if not source.enabled or (selected is not None and source_id not in selected):
                continue
            for artifact in self.discover(source_id, source):
                if periods is None or artifact.period in periods:
                    results.append(self.fetch(artifact, source, force=force))
        return results

    @staticmethod
    def _load_manifest(path: Path) -> dict:
        if not path.exists():
            return {"schema_version": 1, "artifacts": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_manifest(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
