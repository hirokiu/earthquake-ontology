# Earthquake Ontology and Linked Open Data

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Conference](https://img.shields.io/badge/ISWC-2026-blue.svg)](https://iswc2026.semanticweb.org/)

[日本語利用ガイド](docs/USER_GUIDE.ja.md) | [English user guide](docs/USER_GUIDE.en.md)

This repository provides the Earthquake Ontology, Earthquake Linked Open Data,
and command-line tools for acquiring, converting, and auditing earthquake data.
It accompanies the ISWC 2026 Resource Track submission, “Knowledge Graph
Construction for Seismic Data: The Earthquake Ontology and Linked Open Data.”

本リポジトリは、地震オントロジー、地震LOD、および外部機関の地震データを取得・RDF変換・
検査するコマンドラインツールを提供します。

## Supported sources / 対応データソース

- JMA monthly seismic-intensity data / 気象庁月次震度データ
- JMA provisional daily hypocenters / 気象庁日別暫定震源リスト
- USGS FDSN Event QuakeML
- EarthScope FDSN StationXML
- J-SHIS ground-motion flat file, including K-NET/KiK-net-derived records

Source definitions are validated from [`config/sources.yaml`](config/sources.yaml).
Downloaded originals are stored immutably by SHA-256, and generated RDF records
retain links to their authoritative source.

## Quick start / クイックスタート

Python 3.10 or later is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

```bash
earthquake-data-fetch --source fdsn_events_usgs --period 2025 --list
earthquake-data-fetch --source fdsn_events_usgs --period 2025
earthquake-rdf-convert fdsn-events input.xml output.ttl \
  --source-uri 'https://earthquake.usgs.gov/fdsnws/event/1/query?...'
earthquake-rdf-audit output.ttl --require-source
```

See the [Japanese](docs/USER_GUIDE.ja.md) or
[English](docs/USER_GUIDE.en.md) guide for configuration, every converter,
validation, storage, and operational update procedures.

## Commands / コマンド

| Command | Purpose |
| --- | --- |
| `earthquake-data-fetch` | Discover and immutably archive provider data |
| `earthquake-data-organize` | Organize legacy files by filesystem creation date |
| `earthquake-rdf-convert` | Convert provider formats to RDF/Turtle |
| `earthquake-rdf-audit` | Stream-check generated Turtle for common defects |
| `earthquake-rdf-snapshot` | Rebuild a complete named-graph N-Quads snapshot |
| `earthquake-rdf-publish` | Fetch, validate, test, and blue-green publish from cron |

## Repository structure / リポジトリ構成

```text
config/                         Source and HTTP settings
docs/                           User and operational documentation
ontology/jp-earthquake.ttl      Earthquake Ontology
shapes/core.shacl.ttl           Core SHACL constraints
src/earthquake_ontology/        Acquisition, parsers, models, and RDF builder
tests/                          Automated tests
```

## Public resources / 公開リソース

- [SPARQL endpoint](https://seismic.balog.jp/sparql/)
- [Ontology](https://seismic.balog.jp/ontology/)
- [GitHub releases](https://github.com/hirokiu/earthquake-ontology/releases)

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Publication must follow [`docs/data-lifecycle.md`](docs/data-lifecycle.md):
archive the source, create and validate a new snapshot, back up the active graph,
and replace the complete target graph.

For a production clone, QLever blue-green deployment, nginx switching, rollback,
and cron configuration, see [`docs/PRODUCTION_UPDATE.ja.md`](docs/PRODUCTION_UPDATE.ja.md).

Generated output can be written as Turtle, N-Triples, or named-graph N-Quads.
When the output path is omitted, files are stored below
`data/YYYY-MM-DD/{converter}/{format}/`. N-Quads is convenient for a QLever
index that preserves named graphs. Automatic filenames include both provider
and dataset type, for example `usgs-fdsn-events-1960.nq`.

J-SHIS conversion supports `--split-by-year`, which retains the complete output
and adds self-contained files for each earthquake origin year. JMA and J-SHIS
timestamps carry the JST `+09:00` offset; FDSN timestamps preserve the offset
supplied by QuakeML (`Z` is serialized as `+00:00`).

All converters support `--split-by-entity`. It replaces a mixed RDF output with
separate `*-hypocenters`, `*-stations`, and `*-observed-waves` files; the last
category includes J-SHIS strong-motion records. It can be combined with
`--split-by-year`. Hypocenters use the URI-valued `jpe:detarminatedBy` property
for the organization that determined the solution, while
`jpe:determinatedWay` is reserved for the determination method or source flag.
Generated Turtle binds the established `http://schema.org/` vocabulary exactly
as `schema:`; RDFLib's conflicting default binding is replaced so `schema1:` is
never emitted.

## License and attribution

The ontology is distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Provider data remains subject to each provider’s terms. Use of the J-SHIS flat
file requires its specified citations, including DOI `10.17598/NIED.0032`.
