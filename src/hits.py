"""Plain power-iteration HITS.

`nx.hits` exists but raises in older versions when the graph has dangling
nodes; the math is two lines anyway, so we keep it inline.
"""

from __future__ import annotations

import networkx as nx


def hits(g: nx.DiGraph, iters: int = 50) -> tuple[dict[str, float], dict[str, float]]:
    n = g.number_of_nodes()
    if n == 0:
        return {}, {}

    nodes = list(g.nodes())
    idx = {u: i for i, u in enumerate(nodes)}
    out_neigh: list[list[int]] = [[] for _ in nodes]
    in_neigh:  list[list[int]] = [[] for _ in nodes]
    for u, v in g.edges():
        out_neigh[idx[u]].append(idx[v])
        in_neigh[idx[v]].append(idx[u])

    auth = [1.0] * n
    hub  = [1.0] * n

    for _ in range(iters):
        new_auth = [sum(hub[j] for j in in_neigh[i])  for i in range(n)]
        new_hub  = [sum(new_auth[j] for j in out_neigh[i]) for i in range(n)]
        a_norm = sum(x * x for x in new_auth) ** 0.5 or 1.0
        h_norm = sum(x * x for x in new_hub)  ** 0.5 or 1.0
        auth = [x / a_norm for x in new_auth]
        hub  = [x / h_norm for x in new_hub]

    authorities = {nodes[i]: auth[i] for i in range(n)}
    hubs        = {nodes[i]: hub[i]  for i in range(n)}
    return authorities, hubs
