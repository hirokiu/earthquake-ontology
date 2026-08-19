# Data lifecycle

## Principles

- The external provider remains the authoritative source. The LOD is an RDF
  representation of that source, not a replacement for it.
- Use `prov:wasDerivedFrom` or `dcterms:source` on a resource whenever the
  provider exposes a stable URI for the corresponding record.
- Store the provider dataset URI, retrieval time, original checksum, converter
  version, and previous snapshot on every generated dataset snapshot.
- Published snapshots are immutable. Corrections to historical earthquakes are
  represented by a newly generated snapshot, not by modifying the old snapshot.
- Serving only the latest graph is an operational choice; archived graphs and
  source files remain recoverable.

## Named graph convention

Use one immutable graph per provider, dataset, covered period, and retrieval:

```text
https://seismic.balog.jp/graph/{provider}/{dataset}/{period}/{retrieved-at}
```

Example:

```text
https://seismic.balog.jp/graph/jma/monthly-intensity/2026-07/2026-08-19T120000Z
```

Keep snapshot metadata in a separate catalog graph. The metadata resource is a
`jpe:DatasetSnapshot` and records at least:

- `jpe:snapshotOf`
- `prov:generatedAtTime`
- `prov:wasDerivedFrom`
- `jpe:sourceChecksum`
- `jpe:previousSnapshot`, when one exists
- converter software version

## Full-refresh publication

1. Download the provider source into an immutable staging directory.
2. Record its URI, retrieval headers, retrieval time, and SHA-256 checksum.
3. Convert the complete covered period into a new staging named graph.
4. Run Turtle parsing, SHACL validation, referential checks, and count checks.
5. Back up the currently served graph and its catalog metadata.
6. Load the new graph without changing the currently served graph.
7. Re-run validation and counts against the SPARQL store.
8. Atomically switch the current-graph alias or application configuration.
9. Retain the previous graph and original source according to the retention
   policy. If publication fails, keep serving the previous graph.

This process treats an update as a complete replacement of the covered period,
so provider corrections to older events are included without implementing
fragile record-level patches.
