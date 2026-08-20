"""Safe, cron-oriented full-refresh publication orchestration."""

from __future__ import annotations

import fcntl
import json
import os
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx
import yaml

from .acquisition import DataFetcher
from .config import load_settings


CHANGED_STATUSES = {"downloaded"}


@dataclass(frozen=True)
class CommandResult:
    phase: str
    command: tuple[str, ...]


def load_publication_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("publication config must be a YAML mapping")
    required = {"source_config", "state_directory", "snapshot_directory", "build_command", "store"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"publication config is missing: {', '.join(sorted(missing))}")
    store = data["store"]
    if not isinstance(store, dict) or store.get("strategy") != "blue_green":
        raise ValueError("store.strategy must be blue_green")
    for name in ("prepare_command", "start_command", "activate_command"):
        if not store.get(name):
            raise ValueError(f"store.{name} is required")
    return data


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"publication is already running: {path}") from exc
        yield


def _expand_command(command: list[str], values: dict[str, str]) -> list[str]:
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("commands must be non-empty YAML string arrays")
    return [item.format_map(values) for item in command]


def run_command(phase: str, command: list[str], values: dict[str, str], *, dry_run: bool) -> CommandResult:
    expanded = _expand_command(command, values)
    print(json.dumps({"phase": phase, "command": shlex.join(expanded), "dry_run": dry_run}, ensure_ascii=False))
    if not dry_run:
        subprocess.run(expanded, check=True)
    return CommandResult(phase, tuple(expanded))


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"active_slot": "blue", "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def execute_query_tests(endpoint: str, tests: list[dict[str, Any]], root: Path) -> None:
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for test in tests:
            name = str(test.get("name") or test.get("query_file") or "query")
            query_file = (root / str(test["query_file"])).resolve()
            query = query_file.read_text(encoding="utf-8")
            response = None
            for attempt in range(10):
                try:
                    response = client.get(
                        endpoint,
                        params={"query": query, "format": "application/sparql-results+json"},
                        headers={"Accept": "application/sparql-results+json"},
                    )
                    break
                except httpx.ConnectError:
                    if attempt == 9:
                        raise
                    time.sleep(2)
            assert response is not None
            response.raise_for_status()
            payload = response.json()
            bindings = payload.get("results", {}).get("bindings", [])
            minimum = int(test.get("minimum_rows", 0))
            if len(bindings) < minimum:
                raise RuntimeError(f"SPARQL test {name!r} returned {len(bindings)} rows; expected >= {minimum}")
            print(json.dumps({"phase": "query_test", "name": name, "rows": len(bindings)}, ensure_ascii=False))


def publish(config_path: Path, *, force: bool = False, dry_run: bool = False) -> int:
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_publication_config(config_path)
    state_dir = (root / config["state_directory"]).resolve()
    snapshot_root = (root / config["snapshot_directory"]).resolve()
    state_file = state_dir / "publication-state.json"
    lock_file = state_dir / "publication.lock"

    with exclusive_lock(lock_file):
        source_config = (root / config["source_config"]).resolve()
        settings = load_settings(source_config)
        selected_sources = config.get("sources")
        with DataFetcher(settings) as fetcher:
            results = fetcher.fetch_sources(selected_sources)
        changed = [result for result in results if result.status in CHANGED_STATUSES]
        print(json.dumps({
            "phase": "fetch", "checked": len(results), "changed": len(changed),
            "statuses": {status: sum(item.status == status for item in results) for status in sorted({item.status for item in results})},
        }, ensure_ascii=False))
        if not changed and not force:
            print(json.dumps({"phase": "complete", "status": "no_change"}))
            return 0

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot = snapshot_root / run_id
        state = _load_state(state_file)
        active = state.get("active_slot", "blue")
        candidate = "green" if active == "blue" else "blue"
        store = config["store"]
        slot_ports = store.get("slot_ports", {"blue": 7011, "green": 7012})
        values = {
            "root": str(root), "run_id": run_id, "snapshot": str(snapshot),
            "active_slot": active, "candidate_slot": candidate,
            "active_port": str(slot_ports[active]), "candidate_port": str(slot_ports[candidate]),
        }
        snapshot.mkdir(parents=True, exist_ok=False)
        (snapshot / "fetch-results.json").write_text(
            json.dumps([result.__dict__ | {"artifact": result.artifact.__dict__} for result in results], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        run_command("build", config["build_command"], values, dry_run=dry_run)
        for command in config.get("validation_commands", []):
            run_command("validate", command, values, dry_run=dry_run)
        run_command("prepare_candidate", store["prepare_command"], values, dry_run=dry_run)
        run_command("start_candidate", store["start_command"], values, dry_run=dry_run)

        candidate_endpoint = str(store["candidate_endpoint"]).format_map(values)
        if not dry_run:
            execute_query_tests(candidate_endpoint, config.get("query_tests", []), root)
        run_command("activate", store["activate_command"], values, dry_run=dry_run)
        public_endpoint = store.get("public_endpoint")
        if public_endpoint and not dry_run:
            try:
                execute_query_tests(str(public_endpoint), config.get("query_tests", []), root)
            except Exception:
                rollback_values = values | {
                    "candidate_slot": active, "candidate_port": values["active_port"],
                    "active_slot": candidate, "active_port": values["candidate_port"],
                }
                rollback_command = store.get("rollback_command", store["activate_command"])
                run_command("rollback", rollback_command, rollback_values, dry_run=False)
                raise

        if not dry_run:
            state["active_slot"] = candidate
            state["last_successful_run"] = run_id
            state.setdefault("history", []).append({
                "run_id": run_id, "slot": candidate, "previous_slot": active,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            state["history"] = state["history"][-20:]
            _write_state(state_file, state)
        print(json.dumps({"phase": "complete", "status": "published", "run_id": run_id, "slot": candidate}))
        return 0
