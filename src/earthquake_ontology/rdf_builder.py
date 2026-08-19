"""RDF construction isolated from provider-specific parsing."""

from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from urllib.parse import quote

from rdflib import Graph, Literal, RDF, RDFS, SKOS, URIRef, XSD

from .model import DatasetSnapshot, Hypocenter, Observation, ParsedDataset, Station, StrongMotionRecord
from .namespaces import DCAT, DCTERMS, IC, JPE, PROV, SCHEMA


def _decimal(value: Decimal) -> Literal:
    return Literal(value, datatype=XSD.decimal)


def _datetime(value) -> Literal:
    return Literal(value.isoformat(), datatype=XSD.dateTime)


class RdfBuilder:
    def new_graph(self) -> Graph:
        graph = Graph()
        for prefix, namespace in (
            ("dcat", DCAT), ("dcterms", DCTERMS), ("ic", IC), ("jpe", JPE),
            ("prov", PROV), ("schema", SCHEMA), ("skos", SKOS),
        ):
            graph.bind(prefix, namespace)
        return graph

    def add_hypocenter(self, graph: Graph, item: Hypocenter) -> URIRef:
        subject = URIRef(item.uri)
        graph.add((subject, RDF.type, JPE.hypocenter))
        graph.add((subject, JPE.originTime, _datetime(item.origin_time)))
        graph.add((subject, SCHEMA.latitude, _decimal(item.latitude)))
        graph.add((subject, SCHEMA.longitude, _decimal(item.longitude)))
        graph.add((subject, PROV.wasDerivedFrom, URIRef(item.source_uri)))
        if item.label_ja:
            graph.add((subject, RDFS.label, Literal(item.label_ja, lang="ja")))
            graph.add((subject, SKOS.prefLabel, Literal(item.label_ja, lang="ja")))
        if item.label_en:
            graph.add((subject, RDFS.label, Literal(item.label_en, lang="en")))
        for predicate, value in (
            (JPE.depth, item.depth_m), (JPE.magnitude, item.magnitude),
        ):
            if value is not None:
                graph.add((subject, predicate, _decimal(value)))
        for predicate, value in (
            (JPE.magnitudeType, item.magnitude_type), (JPE.catalog, item.catalog),
            (JPE.determinatedWay, item.determination_method),
            (JPE.hypocenterKinds, item.record_type), (JPE.shindo, item.maximum_intensity),
            (JPE.withTravelTimeTable, item.travel_time_table),
        ):
            if value is not None:
                graph.add((subject, predicate, Literal(value)))
        if item.observed_station_count is not None:
            graph.add((subject, JPE.observedStationNum, Literal(item.observed_station_count, datatype=XSD.nonNegativeInteger)))
        return subject

    def add_observation(self, graph: Graph, item: Observation) -> URIRef:
        subject = URIRef(item.uri)
        graph.add((subject, RDF.type, JPE.observedWave))
        graph.add((subject, SCHEMA.startTime, _datetime(item.start_time)))
        graph.add((subject, JPE.hasHypocenter, URIRef(item.hypocenter_uri)))
        graph.add((subject, JPE.observedBy, URIRef(item.station_uri)))
        graph.add((subject, PROV.wasDerivedFrom, URIRef(item.source_uri)))
        if item.intensity is not None:
            graph.add((subject, JPE.shindo, Literal(item.intensity)))
        if item.calculated_intensity is not None:
            graph.add((subject, JPE.calcShindo, _decimal(item.calculated_intensity)))
        return subject

    def add_station(self, graph: Graph, item: Station) -> URIRef:
        subject = URIRef(item.uri)
        graph.add((subject, RDF.type, JPE.observer))
        graph.add((subject, JPE.stationIdentifier, Literal(item.identifier)))
        graph.add((subject, SCHEMA.latitude, _decimal(item.latitude)))
        graph.add((subject, SCHEMA.longitude, _decimal(item.longitude)))
        graph.add((subject, PROV.wasDerivedFrom, URIRef(item.source_uri)))
        if item.label_ja:
            graph.add((subject, RDFS.label, Literal(item.label_ja, lang="ja")))
            graph.add((subject, SKOS.prefLabel, Literal(item.label_ja, lang="ja")))
        if item.label_en:
            graph.add((subject, RDFS.label, Literal(item.label_en, lang="en")))
        if item.elevation_m is not None:
            graph.add((subject, SCHEMA.elevation, _decimal(item.elevation_m)))
        if item.network:
            graph.add((subject, JPE.observationNetwork, Literal(item.network)))
        if item.available_from:
            graph.add((subject, SCHEMA.availabilityStarts, _datetime(item.available_from)))
        if item.available_until:
            graph.add((subject, SCHEMA.availabilityEnds, _datetime(item.available_until)))
        if item.address:
            address = item.address
            graph.add((subject, SCHEMA.address, Literal(address.full_address, lang=address.language)))
            address_uri = address.address_uri or "https://uedayou.net/loa/" + quote(address.full_address, safe="")
            graph.add((subject, IC["住所"], URIRef(address_uri)))
            for predicate, value, language in (
                (IC["都道府県"], address.prefecture, address.language),
                (IC["都道府県コード"], address.prefecture_code, None),
                (IC["市区町村"], address.municipality, address.language),
                (IC["市区町村コード"], address.municipality_code, None),
            ):
                if value:
                    graph.add((subject, predicate, Literal(value, lang=language)))
        return subject

    def add_snapshot(self, graph: Graph, item: DatasetSnapshot) -> URIRef:
        subject = URIRef(item.uri)
        graph.add((subject, RDF.type, JPE.DatasetSnapshot))
        graph.add((subject, JPE.snapshotOf, URIRef(item.dataset_uri)))
        graph.add((subject, PROV.wasDerivedFrom, URIRef(item.source_uri)))
        graph.add((subject, PROV.generatedAtTime, _datetime(item.generated_at)))
        graph.add((subject, JPE.sourceChecksum, Literal(item.source_sha256, datatype=XSD.hexBinary)))
        graph.add((subject, DCAT.distribution, URIRef(item.graph_uri)))
        if item.previous_snapshot_uri:
            graph.add((subject, JPE.previousSnapshot, URIRef(item.previous_snapshot_uri)))
        if item.converter_version:
            graph.add((subject, PROV.value, Literal(item.converter_version)))
        return subject

    def add_strong_motion_record(self, graph: Graph, item: StrongMotionRecord) -> URIRef:
        subject = URIRef(item.uri)
        graph.add((subject, RDF.type, JPE.StrongMotionRecord))
        graph.add((subject, JPE.recordIdentifier, Literal(item.identifier)))
        graph.add((subject, JPE.observedBy, URIRef(item.station_uri)))
        graph.add((subject, JPE.hasHypocenter, URIRef(item.hypocenter_uri)))
        graph.add((subject, PROV.wasDerivedFrom, URIRef(item.source_uri)))
        if item.file_basename:
            graph.add((subject, JPE.fileBaseName, Literal(item.file_basename)))
        if item.sample_count is not None:
            graph.add((subject, JPE.sampleCount, Literal(item.sample_count, datatype=XSD.nonNegativeInteger)))
        for predicate, value in (
            (JPE.samplingFrequency, item.sampling_frequency_hz),
            (JPE.peakGroundAccelerationNS, item.pga_ns),
            (JPE.peakGroundAccelerationEW, item.pga_ew),
            (JPE.peakGroundAccelerationUD, item.pga_ud),
            (JPE.peakGroundVelocityNS, item.pgv_ns),
            (JPE.peakGroundVelocityEW, item.pgv_ew),
            (JPE.peakGroundVelocityUD, item.pgv_ud),
            (JPE.spectrumIntensity, item.spectrum_intensity),
            (JPE.instrumentalIntensity, item.instrumental_intensity),
            (JPE.faultDistance, item.fault_distance_km),
        ):
            if value is not None:
                graph.add((subject, predicate, _decimal(value)))
        return subject

    def build_dataset(self, data: ParsedDataset) -> Graph:
        graph = self.new_graph()
        for item in data.hypocenters:
            self.add_hypocenter(graph, item)
        for item in data.stations:
            self.add_station(graph, item)
        for item in data.observations:
            self.add_observation(graph, item)
        for item in data.strong_motion_records:
            self.add_strong_motion_record(graph, item)
        return graph
