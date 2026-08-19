# Earthquake Ontology Tool User Guide

[日本語](USER_GUIDE.ja.md) | [README](../README.md)

## 1. Overview

The tools acquire earthquake data published by external organizations and
convert provider formats through shared domain models into RDF/Turtle conforming
to the Earthquake Ontology. Source bytes are never overwritten; each revision is
stored in an immutable SHA-256-addressed directory.

| Command | Purpose |
| --- | --- |
| `earthquake-data-fetch` | Discover, download, and archive source artifacts |
| `earthquake-rdf-convert` | Convert provider formats to Turtle |
| `earthquake-rdf-audit` | Stream-audit large Turtle files |

## 2. Installation

Use Python 3.10 or later.

```bash
git clone https://github.com/hirokiu/earthquake-ontology.git
cd earthquake-ontology
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

```bash
earthquake-data-fetch --help
earthquake-rdf-convert --help
earthquake-rdf-audit --help
```

## 3. Acquiring data

Sources are declared in [`config/sources.yaml`](../config/sources.yaml). Discover
artifacts without downloading them first:

```bash
earthquake-data-fetch --source jma_daily_hypocenters --list
earthquake-data-fetch --source fdsn_events_usgs --period 2025 --list
```

`--source` and `--period` may be repeated. Omitting them selects every enabled
source and every discovered period, so constrain the first run explicitly.

```bash
earthquake-data-fetch --source jma_daily_hypocenters --period 20260817
earthquake-data-fetch --source fdsn_events_usgs --period 2025
earthquake-data-fetch --source jshis_ground_motion_flatfile --period v2024
```

Artifacts and manifests are stored as follows:

```text
var/raw/{source-id}/{period}/{sha256}/{filename}
var/manifests/{source-id}.json
```

Subsequent requests use `ETag` or `Last-Modified` when provided. Changed bytes
create a new SHA-256 directory and retain the previous revision. `--force`
ignores conditional-request metadata but does not overwrite archived bytes.

## 4. Converting data to RDF

Every converter requires `--source-uri`, which identifies the authoritative
input artifact or API request. Existing output files are rejected unless
`--force` is explicitly supplied.

### 4.1 JMA provisional daily hypocenters

```bash
earthquake-rdf-convert jma-daily daily-20260817.html daily-20260817.ttl \
  --source-uri https://www.data.jma.go.jp/eqev/data/daily_map/20260817.html
```

Daily values are provisional and may later be corrected. Do not treat them as
the same snapshot as the finalized monthly catalog.

### 4.2 JMA monthly intensity data

Safely extract the fixed-width data file from the acquired `iYYYY.zip` into a
working directory before conversion. Shift_JIS is the default encoding.

```bash
earthquake-rdf-convert jma-intensity i2022.dat i2022.ttl \
  --source-uri https://www.data.jma.go.jp/eqev/data/bulletin/data/shindo/i2022.zip
```

Snapshot metadata can be generated at the same time:

```bash
earthquake-rdf-convert jma-intensity i2022.dat i2022.ttl \
  --source-uri https://www.data.jma.go.jp/eqev/data/bulletin/data/shindo/i2022.zip \
  --snapshot-output i2022.snapshot.ttl \
  --snapshot-uri https://seismic.balog.jp/snapshot/jma/2022/20260819T000000Z \
  --dataset-uri https://www.data.jma.go.jp/eqev/data/bulletin/shindo.html \
  --graph-uri https://seismic.balog.jp/graph/jma/intensity/2022/20260819T000000Z
```

### 4.3 FDSN events (QuakeML)

```bash
earthquake-rdf-convert fdsn-events events-2025.xml events-2025.ttl \
  --source-uri 'https://earthquake.usgs.gov/fdsnws/event/1/query?...'
```

The parser selects `preferredOriginID` and `preferredMagnitudeID`. Historical
IRIS public IDs are normalized to the URI form already published by this project.

### 4.4 FDSN stations (StationXML)

```bash
earthquake-rdf-convert fdsn-stations stations.xml stations.ttl \
  --source-uri 'https://service.earthscope.org/fdsnws/station/1/query?...'
```

A global station response is large, so `fdsn_stations_earthscope` is disabled by
default. Enable it in deployment YAML only after constraining its URL by network
or time range.

### 4.5 J-SHIS ground-motion flat file

```bash
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip flatfile-v2024.ttl \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip
```

The parser reads `site_schema.tsv`, `source_schema.tsv`, and `smrec_schema.tsv`
inside the ZIP and converts K-NET/KiK-net stations, hypocenters, and core
strong-motion metrics. The current RDF builder retains the graph in memory, so
provide sufficient memory for the approximately 2 GB full edition. Publications
must include the citations required by J-SHIS, including DOI `10.17598/NIED.0032`.

### 4.6 Invalid records

By default, any invalid record aborts conversion. For investigation only,
`--allow-issues` reports invalid records as JSON Lines on standard error and
writes valid records:

```bash
earthquake-rdf-convert fdsn-events input.xml output.ttl \
  --source-uri https://example.org/source.xml --allow-issues
```

Do not use `--allow-issues` in unattended publication workflows; correct the
underlying problem instead.

## 5. Auditing Turtle

```bash
earthquake-rdf-audit output.ttl --require-source
earthquake-rdf-audit output-directory/ --require-source --json
```

The exit status is `0` when no finding is detected and `1` otherwise. Set
`--max-findings 0` for no limit. This bounded-memory audit detects common defects;
publication also requires RDF parsing and SHACL validation with
[`shapes/core.shacl.ttl`](../shapes/core.shacl.ttl).

## 6. Configuration and credentials

Do not store secrets in YAML. Environment variables use the `EQ_` prefix and
`__` nesting delimiter and take precedence over YAML.

```bash
export EQ_HTTP__RETRIES=5
export EQ_NIED_USERNAME='registered-user'
export EQ_NIED_PASSWORD='secret'
```

The authenticated K-NET/KiK-net direct-download example is disabled by default.
Enable it only in private configuration and supply credentials through the
environment. Select another configuration file with `--config`:

```bash
earthquake-data-fetch --config config/production.yaml --source nied_knet_example
```

## 7. Update and publication workflow

Because providers may revise historical records, use complete graph replacement
instead of incremental SPARQL edits:

1. Archive the source with its SHA-256 digest.
2. Generate a complete new RDF snapshot.
3. Run Turtle parsing, the streaming audit, and SHACL validation.
4. Back up the active named graph.
5. Replace the complete target graph.
6. Record provenance between the old and new snapshots.

See [`data-lifecycle.md`](data-lifecycle.md) for the operational policy.

## 8. Development checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

`var/` and `tmp/` are ignored by Git. Review each provider’s license,
attribution, and citation requirements before publishing derived data.
