"""Persist the crawl dataset itself — one of the required deliverables.

Two files end up under output/dataset/:

    pages.jsonl    one JSON object per page: {url, title, outlinks: [...]}
    edges.csv      flat (src, dst) edge list
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from .parse import CrawlData


def write(data: CrawlData, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    out_by_src: dict[str, list[str]] = defaultdict(list)
    for src, dst in data.edges:
        out_by_src[src].append(dst)

    pages_path = out_dir / "pages.jsonl"
    with pages_path.open("w", encoding="utf-8") as fh:
        for url in sorted(data.pages):
            page = data.pages[url]
            record = {
                "url": url,
                "title": page.title,
                "outlinks": sorted(out_by_src.get(url, [])),
            }
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")

    edges_path = out_dir / "edges.csv"
    with edges_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["src", "dst"])
        for src, dst in sorted(data.edges):
            writer.writerow([src, dst])

    return out_dir
