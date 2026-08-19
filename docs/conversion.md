# Conversion pipeline

Provider parsers produce source-independent domain models. Only `RdfBuilder`
creates RDF, so namespace, datatype, provenance, and escaping rules are shared
by JMA, FDSN, K-NET, and KiK-net conversions.

FDSN QuakeML maps to `Hypocenter`, StationXML maps to `Station`, and the common
`RdfBuilder` produces the ontology terms. The new path has no ObsPy runtime
dependency.

## JMA monthly intensity files

Install the package in a virtual environment, then run:

```bash
earthquake-rdf-convert jma-intensity input/i2019.dat output/i2019.ttl \
  --source-uri https://provider.example/path/i2019.dat \
  --snapshot-output output/i2019.snapshot.ttl \
  --snapshot-uri https://seismic.balog.jp/snapshot/jma/2019/20260819T030000Z \
  --dataset-uri https://provider.example/dataset/monthly-intensity \
  --graph-uri https://seismic.balog.jp/graph/jma/monthly-intensity/2019/20260819T030000Z
```

The default source encoding is Shift_JIS. Use `--encoding` when a provider file
uses another encoding.

Conversion stops if a malformed record is found. `--allow-issues` writes only
valid records and reports rejected records as JSON Lines on standard error; it
is intended for investigation, not unattended publication.

Existing output files are never replaced unless `--force` is explicitly set.
Production publication must still follow the backup and named-graph procedure
in `data-lifecycle.md`; `--force` only controls local artifact files.

The initial parser covers the hypocenter and seismic-intensity observation
records handled by the legacy `mkTriple_hypo.py`. It does not yet fetch source
files, parse station master files, or publish to SPARQL.
