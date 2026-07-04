"""matplotlib output. Headless backend so it works under SSH."""

from __future__ import annotations
import networkx as nx
import matplotlib.pyplot as plt

import math
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")


def loglog_scatter(degrees: list[int], title: str, path: Path) -> None:
    counts = Counter(d for d in degrees if d > 0)
    if not counts:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    xs = sorted(counts)
    ys = [counts[x] for x in xs]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(xs, ys, s=18, alpha=0.7)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("degree (log)")
    ax.set_ylabel("count (log)")
    ax.set_title(title)
    ax.grid(True, which="both", linestyle="--", linewidth=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fit_slope(centres: list[float], density: list[float]) -> float | None:
    """Least-squares slope of log10(P(k)) vs log10(k) over the non-empty bins.

    This is the power-law exponent: a distribution P(k) ~ k^slope plots as a
    straight line with this gradient on log-log axes. Returns None when there
    aren't enough points to fit a line.
    """
    pts = [(math.log10(c), math.log10(d))
           for c, d in zip(centres, density) if d > 0]
    if len(pts) < 2:
        return None
    n = len(pts)
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts)
    sxy = sum(x * y for x, y in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    return (n * sxy - sx * sy) / denom


def logbin_histogram(degrees: list[int], title: str, path: Path, bins: int = 20) -> float | None:
    """Log-binned PDF — Newman's recommended way of viewing a heavy tail.

    Equal-width bins on a log axis under-sample the tail badly; here we use
    geometric bin widths and divide each bin's count by its width. Returns the
    fitted power-law slope (or None) so the caller can record it.
    """
    positive = [d for d in degrees if d > 0]
    if not positive:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)

    lo, hi = min(positive), max(positive)
    if lo == hi:
        # Degenerate — show as a single bar so the plot still renders.
        fig, ax = plt.subplots(figsize=(6, 4.5))
        ax.bar([lo], [len(positive)], width=0.8)
        ax.set_title(title)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return None

    edges = [lo * (hi / lo) ** (i / bins) for i in range(bins + 1)]
    counts = [0] * bins
    for d in positive:
        i = min(int(math.log(d / lo) / math.log(hi / lo) * bins), bins - 1)
        counts[i] += 1
    widths = [edges[i + 1] - edges[i] for i in range(bins)]
    n = len(positive)
    density = [c / (w * n) if w > 0 else 0 for c, w in zip(counts, widths)]
    centres = [(edges[i] * edges[i + 1]) ** 0.5 for i in range(bins)]

    slope = _fit_slope(centres, density)
    if slope is not None:
        title = f"{title}  (slope {slope:.2f})"

    fig, ax = plt.subplots(figsize=(6, 4.5))
    nonzero = [(c, d) for c, d in zip(centres, density) if d > 0]
    if nonzero:
        ax.plot([c for c, _ in nonzero], [
                d for _, d in nonzero], "o-", linewidth=1.2)
    if slope is not None and nonzero:
        # Draw the fitted line through the geometric-mean point of the data.
        xs = [c for c, _ in nonzero]
        ys = [d for _, d in nonzero]
        x0 = 10 ** (sum(math.log10(x) for x in xs) / len(xs))
        y0 = 10 ** (sum(math.log10(y) for y in ys) / len(ys))
        fit_x = [min(xs), max(xs)]
        fit_y = [y0 * (x / x0) ** slope for x in fit_x]
        ax.plot(fit_x, fit_y, "--", color="crimson", linewidth=1.0,
                label=f"fit: slope {slope:.2f}")
        ax.legend(fontsize=8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("degree")
    ax.set_ylabel("P(k) (log-binned)")
    ax.set_title(title)
    ax.grid(True, which="both", linestyle="--", linewidth=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return slope


def snapshot(graph: nx.DiGraph, path: Path, max_nodes: int = 500) -> None:
    if graph.number_of_nodes() == 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)

    if graph.number_of_nodes() > max_nodes:
        keep = {u for u, _ in sorted(
            graph.degree, key=lambda kv: kv[1], reverse=True)[:max_nodes]}
        sub = graph.subgraph(keep).copy()
    else:
        sub = graph

    pos = nx.spring_layout(sub, k=0.25, iterations=40, seed=42)
    fig, ax = plt.subplots(figsize=(9, 9))
    sizes = [10 + 2 * sub.degree(u) for u in sub.nodes()]
    nx.draw_networkx_edges(sub, pos, alpha=0.15, arrows=False, ax=ax)
    nx.draw_networkx_nodes(sub, pos, node_size=sizes, alpha=0.7, ax=ax)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
