# Source acquisition

Operational data sources are declared in `config/sources.yaml`. The file is
validated with Pydantic Settings before any network or filesystem operation.
Unknown keys, malformed URLs, unsafe destination names, and invalid discovery
patterns stop execution.

YAML contains non-secret defaults and source metadata. Environment variables
override YAML using the `EQ_` prefix and `__` for nested fields. For example:

```bash
export EQ_HTTP__RETRIES=5
export EQ_NIED_USERNAME='registered-user'
export EQ_NIED_PASSWORD='secret'
```

Do not put credentials in YAML or commit them to the repository.

## Discover available JMA archives

```bash
earthquake-data-fetch --source jma_intensity --list
```

Restrict discovery or download to a period:

```bash
earthquake-data-fetch --source jma_intensity --period 2022 --list
earthquake-data-fetch --source jma_intensity --period 2022
```

Download the current JMA intensity station list:

```bash
earthquake-data-fetch --source jma_intensity_stations
```

## Provisional JMA daily hypocenters

`jma_daily_hypocenters` is separate from the finalized monthly catalog. Values
may be corrected later, so each retrieved revision is retained by SHA-256 rather
than overwritten. Convert one page with `earthquake-rdf-convert jma-daily`.

## FDSN events and stations

`fdsn_events_usgs` generates one immutable QuakeML request per calendar year.
The current year is requested again on each run; HTTP validators and the
content-addressed archive retain changed revisions without overwriting earlier
bytes. The historical EarthScope/IRIS event endpoint was retired in 2026, so
new event acquisition uses the USGS FDSN Event service.

`fdsn_stations_earthscope` uses the current EarthScope StationXML endpoint. It
is disabled by default because an unconstrained global station response is
large; enable it in deployment YAML or narrow its query URL first.

```bash
earthquake-data-fetch --source fdsn_events_usgs --period 2025
earthquake-rdf-convert fdsn-events events-2025.xml events-2025.ttl \
  --source-uri 'https://earthquake.usgs.gov/fdsnws/event/1/query?...'
earthquake-rdf-convert fdsn-stations stations.xml stations.ttl \
  --source-uri 'https://service.earthscope.org/fdsnws/station/1/query?...'
```

The QuakeML parser selects the preferred origin and magnitude and preserves
provider-supplied negative depths. Legacy IRIS public IDs are normalized to the
URI form already present in the repository. StationXML uses the existing
`sta-FDSN-{network}.{station}` URI convention.

## J-SHIS ground-motion flat file

`jshis_ground_motion_flatfile` discovers the latest full public ZIP. The first
parser reads `site_schema.tsv`, `source_schema.tsv`, and `smrec_schema.tsv`
directly from the ZIP and converts K-NET/KiK-net stations, sources, and core
strong-motion metrics. The original TSV retains all response-spectrum columns
for later ontology extensions. Publications must cite DOI `10.17598/NIED.0032`
and the upstream data sources specified by J-SHIS.

```bash
earthquake-data-fetch --source jma_daily_hypocenters --period 20260817
earthquake-data-fetch --source jshis_ground_motion_flatfile --period v2024
earthquake-rdf-convert jshis-flatfile flatfile-v2024.zip output.ttl \
  --source-uri https://www.j-shis.bosai.go.jp/labs/ground-motion-flatfile/data/v2024/flatfile-v2024.zip
```

## Storage behavior

Downloaded bytes are written to a temporary file while SHA-256 is calculated,
then atomically moved to a content-addressed path:

```text
var/raw/{source-id}/{period}/{sha256}/{provider-file-name}
```

The content-addressed original is immutable. A JSON sidecar records source URI,
dataset URI, license URI, retrieval time, response metadata, size, and digest.
The mutable per-source manifest records the latest observed representation.

When available, `ETag` and `Last-Modified` are sent as conditional request
headers. A `304 Not Modified` response does not create a new artifact. If a
server does not support conditional requests, identical bytes resolve to the
existing SHA-256 path.

HTTP downloads use explicit connect/read timeouts, bounded retries, redirect
handling, a project user agent, and streaming writes. HTTP 429 and transient 5xx
responses are retried with bounded exponential delay.

## K-NET/KiK-net

NIED requires user registration for waveform downloads. The bundled example is
disabled and demonstrates Basic authentication via environment variables. A
private deployment configuration can enable it after credentials and the
desired event-discovery policy have been established. Redistribution and use
must follow NIED's published terms.
