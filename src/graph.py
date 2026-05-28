"""Wrap CrawlData in a NetworkX DiGraph and export it."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from .parse import CrawlData


def build(data: CrawlData) -> nx.DiGraph:
    g = nx.DiGraph()
    for url, page in data.pages.items():
        g.add_node(url, title=page.title)
    g.add_edges_from(data.edges)
    return g


def save(graph: nx.DiGraph, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    graphml = out_dir / "webgraph.graphml"
    gexf = out_dir / "webgraph.gexf"
    nx.write_graphml(graph, graphml, prettyprint=True)
    nx.write_gexf(graph, gexf)
    return graphml, gexf


def largest_wcc(graph: nx.DiGraph) -> nx.DiGraph:
    if graph.number_of_nodes() == 0:
        return graph.copy()
    biggest = max(nx.weakly_connected_components(graph), key=len)
    return graph.subgraph(biggest).copy()
