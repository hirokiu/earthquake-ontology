#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if [[ ! -x .venv/bin/earthquake-rdf-publish ]]; then
  echo "Run: python3 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 2
fi

exec .venv/bin/earthquake-rdf-publish --config "${EQ_PUBLICATION_CONFIG:-config/publication.yaml}" "$@"
