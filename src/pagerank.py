"""PageRank by direct power iteration.

The assignment fixes the parameters: damping = 0.85, 20 iterations, no early
stop. We implement it ourselves rather than calling `nx.pagerank` so the
behaviour matches the spec exactly (the NetworkX implementation iterates until
tolerance is met, which is usually far fewer than 20 steps).
"""

from __future__ import annotations

import networkx as nx


def pagerank(g: nx.DiGraph, d: float = 0.85, iters: int = 20) -> dict[str, float]:
    n = g.number_of_nodes()
    if n == 0:
        return {}

    nodes = list(g.nodes())
    idx = {u: i for i, u in enumerate(nodes)}
    out_deg = [g.out_degree(u) for u in nodes]
    inbound: list[list[int]] = [[] for _ in nodes]
    for u, v in g.edges():
        inbound[idx[v]].append(idx[u])

    r = [1.0 / n] * n
    teleport = (1.0 - d) / n

    for _ in range(iters):
        # Dangling pages: their rank can't flow along an outlink, so spread it
        # uniformly across every node.
        dangling = d * sum(r[i] for i in range(n) if out_deg[i] == 0) / n
        nr = [teleport + dangling] * n
        for i in range(n):
            s = 0.0
            for j in inbound[i]:
                if out_deg[j]:
                    s += r[j] / out_deg[j]
            nr[i] += d * s
        r = nr

    return {nodes[i]: r[i] for i in range(n)}
