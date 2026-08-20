import json
from pathlib import Path
import sys
import tempfile
import unittest
import yaml

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from earthquake_ontology.publication import _expand_command, load_publication_config
from earthquake_ontology.snapshot_cli import build_snapshot, validate_snapshot
from test_fdsn import QUAKEML


class PublicationTest(unittest.TestCase):
    def test_publication_example_is_valid_and_commands_are_argument_arrays(self):
        root = Path(__file__).parents[1]
        config = load_publication_config(root / "config/publication.example.yaml")
        self.assertEqual(config["store"]["strategy"], "blue_green")
        command = _expand_command(config["build_command"], {
            "root": str(root), "snapshot": "/tmp/snapshot", "run_id": "run",
            "active_slot": "blue", "candidate_slot": "green",
            "active_port": "7011", "candidate_port": "7012",
        })
        self.assertEqual(command[1], "build")
        self.assertNotIn("shell", config)

    def test_snapshot_validation_requires_named_publication_graphs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nquads = root / "nquads"
            nquads.mkdir()
            graphs = [
                "https://seismic.balog.jp/graph/jma/monthly-intensity/hypocenters",
                "https://seismic.balog.jp/graph/jma/monthly-intensity/observed-waves",
                "https://seismic.balog.jp/graph/jma/intensity-stations/stations",
                "https://seismic.balog.jp/graph/usgs/fdsn-events/hypocenters",
            ]
            outputs = []
            for index, graph in enumerate(graphs):
                path = nquads / f"{index}.nq"
                path.write_text(f"<https://example/s{index}> <https://example/p> <https://example/o> <{graph}> .\n")
                outputs.append({"path": str(path), "bytes": path.stat().st_size})
            (root / "snapshot-manifest.json").write_text(json.dumps({"outputs": outputs}))
            self.assertEqual(validate_snapshot(root), 0)

    def test_build_snapshot_converts_manifest_artifact_to_named_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_dir = root / "config"
            manifest_dir = root / "manifests"
            raw_dir = root / "raw"
            config_dir.mkdir()
            manifest_dir.mkdir()
            raw_dir.mkdir()
            source = raw_dir / "events.xml"
            source.write_bytes(QUAKEML)
            config = {
                "storage": {"raw_directory": str(raw_dir), "manifest_directory": str(manifest_dir)},
                "sources": {
                    "fdsn_events_usgs": {
                        "enabled": True,
                        "provider": "usgs-fdsn",
                        "dataset_uri": "https://example.test/fdsn/",
                        "discovery": {"type": "direct", "url": "https://example.test/events.xml", "period": "2019"},
                        "destination_name": "events-{period}.xml",
                        "media_type": "application/xml",
                        "parser": "fdsn_quakeml",
                    }
                },
            }
            config_path = config_dir / "sources.yaml"
            config_path.write_text(yaml.safe_dump(config))
            (manifest_dir / "fdsn_events_usgs.json").write_text(json.dumps({
                "artifacts": {"https://example.test/events.xml": {
                    "period": "2019", "url": "https://example.test/events.xml",
                    "path": str(source), "sha256": "fixture",
                }}
            }))
            snapshot = root / "snapshot"
            self.assertEqual(build_snapshot(config_path, snapshot), 0)
            outputs = list((snapshot / "nquads").glob("*-hypocenters.nq"))
            self.assertEqual(len(outputs), 1)
            self.assertIn(
                "<https://seismic.balog.jp/graph/usgs/fdsn-events/hypocenters>",
                outputs[0].read_text(),
            )


if __name__ == "__main__":
    unittest.main()
