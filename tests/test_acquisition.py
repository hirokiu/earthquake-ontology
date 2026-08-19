import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import httpx

from earthquake_ontology.acquisition import DataFetcher
from earthquake_ontology.config import AppSettings, HttpConfig, StorageConfig, load_settings


ROOT = Path(__file__).parents[1]


class AcquisitionTest(unittest.TestCase):
    def test_yaml_is_validated_and_environment_overrides_it(self) -> None:
        with patch.dict(os.environ, {"EQ_HTTP__RETRIES": "1"}, clear=False):
            settings = load_settings(ROOT / "config/sources.yaml")
        self.assertEqual(settings.http.retries, 1)
        self.assertIn("jma_intensity", settings.sources)

    def test_discovers_archives_and_uses_conditional_download(self) -> None:
        configured = load_settings(ROOT / "config/sources.yaml")
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/shindo.html"):
                return httpx.Response(
                    200,
                    text='''<a href="data/shindo/i2021.zip">2021</a><a href="data/shindo/i2022.zip">2022</a>''',
                    request=request,
                )
            if request.headers.get("If-None-Match") == '"revision-1"':
                return httpx.Response(304, request=request)
            return httpx.Response(
                200,
                content=b"PK\x03\x04fixture",
                headers={"ETag": '"revision-1"', "Content-Type": "application/zip"},
                request=request,
            )

        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(
                storage=StorageConfig(
                    raw_directory=Path(directory) / "raw",
                    manifest_directory=Path(directory) / "manifests",
                ),
                http=HttpConfig(retries=0),
                sources={"jma_intensity": configured.sources["jma_intensity"]},
            )
            client = httpx.Client(transport=httpx.MockTransport(handler))
            fetcher = DataFetcher(settings, client=client, sleep=lambda _seconds: None)
            artifacts = fetcher.discover("jma_intensity", settings.sources["jma_intensity"])
            self.assertEqual([artifact.period for artifact in artifacts], ["2021", "2022"])

            first = fetcher.fetch(artifacts[-1], settings.sources["jma_intensity"])
            second = fetcher.fetch(artifacts[-1], settings.sources["jma_intensity"])

            self.assertEqual(first.status, "downloaded")
            self.assertTrue(Path(first.path).exists())
            self.assertEqual(second.status, "not_modified")
            self.assertEqual(requests[-1].headers["If-None-Match"], '"revision-1"')
            manifest = json.loads((settings.storage.manifest_directory / "jma_intensity.json").read_text())
            entry = manifest["artifacts"][artifacts[-1].url]
            self.assertEqual(entry["sha256"], first.sha256)
            self.assertTrue(Path(entry["path"] + ".metadata.json").exists())


if __name__ == "__main__":
    unittest.main()
