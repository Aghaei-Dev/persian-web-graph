"""Driver:  python -m src.cli --dump data/dump --out output --domain sharif.ir"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import analysis, dataset, graph, parse, plots


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build and analyse a Nutch-derived page graph.")
    ap.add_argument("--dump",   type=Path, default=Path("data/dump"),
                    help="Output of scripts/export.sh.")
    ap.add_argument("--out",    type=Path, default=Path("output"),
                    help="Where to write the graph, metrics, plots and dataset.")
    ap.add_argument("--domain", default="sharif.ir",
                    help="Registered domain to keep (e.g. sharif.ir, sharif.ir).")
    args = ap.parse_args(argv)

    raw = parse.read_all(args.dump)
    print(
        f"parsed {len(raw.pages)} urls / {len(raw.edges)} edges from {args.dump}")

    data = parse.restrict_to_domain(raw, args.domain)
    print(
        f"restricted to {args.domain}: {len(data.pages)} nodes, {len(data.edges)} edges")

    g = graph.build(data)
    graphml, gexf = graph.save(g, args.out)
    print(f"wrote {graphml.name} and {gexf.name}")

    dataset.write(data, args.out / "dataset")
    print(f"dataset written to {args.out / 'dataset'}")

    result = analysis.compute(g)
    analysis.write(result, args.out)
    print(f"metrics + top-K tables written to {args.out}")

    plot_dir = args.out / "plots"
    plots.loglog_scatter(list(result["in_degrees"].values()),
                         "In-degree distribution (log-log)",  plot_dir / "in_degree.png")
    plots.loglog_scatter(list(result["out_degrees"].values()),
                         "Out-degree distribution (log-log)", plot_dir / "out_degree.png")
    plots.logbin_histogram(list(result["in_degrees"].values()),
                           "In-degree PDF (log-binned)",  plot_dir / "in_degree_logbin.png")
    plots.logbin_histogram(list(result["out_degrees"].values()),
                           "Out-degree PDF (log-binned)", plot_dir / "out_degree_logbin.png")
    plots.snapshot(graph.largest_wcc(g), plot_dir / "largest_wcc.png")
    print(f"plots written to {plot_dir}")

    print()
    print(f"N={result['nodes']}  E={result['edges']}  "
          f"<k_in>={result['avg_in_degree']:.3f}  "
          f"C={result['avg_clustering']:.3f}  "
          f"WCCs={result['wcc_count']}  "
          f"diam~{result['diameter']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
