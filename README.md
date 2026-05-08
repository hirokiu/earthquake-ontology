# Earthquake Ontology and Linked Open Data 🌍📊

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Conference](https://img.shields.io/badge/ISWC-2026-blue.svg)](https://iswc2026.semanticweb.org/)

This repository contains the official semantic artifacts (Ontology and Linked Open Data) presented in the paper: **"Knowledge Graph Construction for Seismic Data: The Earthquake Ontology and Linked Open Data"** submitted to the Resource Track of the 25th International Semantic Web Conference (ISWC 2026).

## 📖 Overview
Japan and many other regions are highly seismically active. While massive amounts of seismic data are published by various organizations (e.g., JMA, NIED, USGS, FDSN), they exist in fragmented data silos with differing formats and structural semantics. 

To overcome the **Data Integration Challenge** and establish true **Semantic Interoperability**, we developed:
1. **The Earthquake Ontology:** A domain-specific ontology that accurately models the multi-layered physical and observational structure of seismic phenomena (fault slip $\rightarrow$ hypocenter $\rightarrow$ observation waveform).
2. **The Earthquake LOD:** A large-scale knowledge graph integrating domestic data from the Japan Meteorological Agency (JMA) and international data from the International Federation of Digital Seismograph Networks (FDSN).

## 🔗 Public Resources (FAIR Principles)
To adhere to the FAIR (Findable, Accessible, Interoperable, and Reusable) principles, all resources are publicly available and sustainably hosted:

* **SPARQL Endpoint:** [https://seismic.balog.jp/sparql/](https://seismic.balog.jp/sparql/)
* **Ontology URI:** [https://seismic.balog.jp/ontology/](https://seismic.balog.jp/ontology/)
* **Persistent Archive:** This GitHub repository (`ISWC2026` branch) acts as a persistent mirror for the ontology and sample datasets.

## 📦 Data Downloads (GitHub Releases)
For stable versions and larger datasets, please visit the **[Releases](https://github.com/hirokiu/earthquake-ontology/releases)** section of this repository. The release assets include:
* Full RDF dumps of the Earthquake LOD (Turtle format).
* The latest stable version of the Earthquake Ontology.
* 
## 📂 Repository Structure
```text
.
├── ontology/
│   └── jp-earthquake.ttl       # The core Earthquake Ontology definition (Turtle format)
├── datasets/
│   ├── JMA.zip     # Sample LOD converted from JMA Earthquake Monthly Report
│   └── FDSN.zip    # Sample LOD generated from FDSN APIs
└── README.md
