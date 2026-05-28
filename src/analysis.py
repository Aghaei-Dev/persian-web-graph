"""Structural metrics on the page graph + the top-K leaderboards."""

from __future__ import annotations

import csv
import random
from pathlib import Path
from statistics import mean

import networkx as nx

from .graph import largest_wcc
from .hits import hits
from .pagerank import pagerank


# Diameter on the largest WCC is computed by BFS from a sample of sources.
# 300 sources is plenty for ~2k nodes and keeps the wall time under a second.
DIAMETER_SAMPLES = 300


def compute(g: nx.DiGraph) -> dict:
    """Return a flat dict of everything we care about for the report."""
    n = g.number_of_nodes()
    titles = {u: g.nodes[u].get("title", "") for u in g.nodes()}

    in_deg = dict(g.in_degree())
    out_deg = dict(g.out_degree())

    if n:
        c_avg = nx.average_clustering(g.to_undirected())
        avg_in = sum(in_deg.values()) / n
        avg_out = sum(out_deg.values()) / n
    else:
        c_avg = avg_in = avg_out = 0.0

    components = sorted(
        (set(c) for c in nx.weakly_connected_components(g)),
        key=len,
        reverse=True,
    )
    wcc_sizes = [len(c) for c in components]

    diam, avg_path = _diameter(largest_wcc(g))

    pr = pagerank(g, d=0.85, iters=20)
    auth, hub = hits(g, iters=50)

    return {
        "nodes": n,
        "edges": g.number_of_edges(),
        "avg_in_degree": avg_in,
        "avg_out_degree": avg_out,
        "avg_clustering": c_avg,
        "wcc_count": len(components),
        "wcc_top5_sizes": wcc_sizes[:5],
        "largest_wcc_size": wcc_sizes[0] if wcc_sizes else 0,
        "diameter": diam,
        "avg_shortest_path": avg_path,
        "in_degrees": in_deg,
        "out_degrees": out_deg,
        "pagerank": pr,
        "authorities": auth,
        "hubs": hub,
        "titles": titles,
    }


def _diameter(g: nx.DiGraph) -> tuple[int | None, float | None]:
    if g.number_of_nodes() < 2:
        return None, None
    u = g.to_undirected()
    nodes = list(u.nodes())
    sources = (random.Random(42).sample(nodes, DIAMETER_SAMPLES)
               if len(nodes) > DIAMETER_SAMPLES else nodes)
    longest, distances = 0, []
    for src in sources:
        for d in nx.single_source_shortest_path_length(u, src).values():
            if d > 0:
                distances.append(d)
                if d > longest:
                    longest = d
    if not distances:
        return None, None
    return longest, mean(distances)


# ---- output writers ------------------------------------------------------ #

def write(result: dict, out_dir: Path, top_k: int = 10) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir

    _metrics_txt(out / "metrics.txt", result)

    titles = result["titles"]
    _topk_csv(out / "top_in_degree.csv",  result["in_degrees"],  titles, "in_degree", int_value=True, k=top_k)
    _topk_csv(out / "top_out_degree.csv", result["out_degrees"], titles, "out_degree", int_value=True, k=top_k)
    _topk_csv(out / "top_pagerank.csv",   result["pagerank"],    titles, "pagerank",   k=top_k)
    _topk_csv(out / "top_authorities.csv", result["authorities"], titles, "authority", k=top_k)
    _topk_csv(out / "top_hubs.csv",        result["hubs"],        titles, "hub",       k=top_k)

    _full_csv(out / "pagerank_all.csv", result["pagerank"], "pagerank")


def _metrics_txt(path: Path, r: dict) -> None:
    lines = [
        f"Nodes:                {r['nodes']}",
        f"Edges:                {r['edges']}",
        f"Avg in-degree:        {r['avg_in_degree']:.4f}",
        f"Avg out-degree:       {r['avg_out_degree']:.4f}",
        f"Avg clustering coef:  {r['avg_clustering']:.4f}",
        f"WCC count:            {r['wcc_count']}",
        f"WCC sizes (top 5):    {r['wcc_top5_sizes']}",
        f"Largest WCC:          {r['largest_wcc_size']}",
    ]
    if r["diameter"] is not None:
        lines.append(f"Diameter (sampled):   {r['diameter']}")
    if r["avg_shortest_path"] is not None:
        lines.append(f"Avg shortest path:    {r['avg_shortest_path']:.4f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _topk_csv(path: Path, scores: dict, titles: dict, label: str,
              k: int = 10, int_value: bool = False) -> None:
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rank", label, "url", "title"])
        for i, (url, val) in enumerate(ranked, 1):
            cell = int(val) if int_value else f"{val:.8f}"
            writer.writerow([i, cell, url, titles.get(url, "")])


def _full_csv(path: Path, scores: dict, label: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([label, "url"])
        for url, val in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
            writer.writerow([f"{val:.8f}", url])
