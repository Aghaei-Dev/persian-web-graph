"""Read whatever Nutch left under data/dump/ into a flat (pages, edges) form.

Nutch is shipped with a few different dump tools (`readdb`, `readlinkdb`,
`webgraph` + `nodedumper`, `readseg`), and their text formats change between
1.x point releases. Rather than rely on one exact layout, the readers here
just look for URLs in expected positions and stitch the pieces together. If
a future Nutch version reorders fields, the worst case is that we lose
titles — edges still come through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag, urlparse


# Loose URL pattern: tolerates whitespace, quotes, angle brackets around the URL.
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)

# Common ccTLDs that take a 3-part registered domain ("sharif.ir", "bbc.co.uk").
_TWO_LEVEL_SLDS = {"ac", "co", "or", "gov", "net", "edu"}


@dataclass(slots=True)
class Page:
    url: str
    title: str = ""


@dataclass
class CrawlData:
    pages: dict[str, Page] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)

    def page(self, url: str, title: str = "") -> None:
        url = canonical(url)
        if not url:
            return
        existing = self.pages.get(url)
        if existing is None:
            self.pages[url] = Page(url, title)
        elif title and not existing.title:
            existing.title = title

    def edge(self, src: str, dst: str) -> None:
        src, dst = canonical(src), canonical(dst)
        if not src or not dst or src == dst:
            return
        self.page(src)
        self.page(dst)
        self.edges.add((src, dst))


def canonical(url: str) -> str:
    """Strip fragments, lowercase the host, force a `/` path on bare hosts."""
    url = (url or "").strip().strip(".,;)\"'<>")
    if not url:
        return ""
    url, _ = urldefrag(url)
    try:
        p = urlparse(url)
    except ValueError:
        return ""
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    host = p.netloc.lower()
    path = p.path or "/"
    out = f"{p.scheme}://{host}{path}"
    if p.query:
        out += "?" + p.query
    return out


def registered_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in _TWO_LEVEL_SLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


# ---- individual readers -------------------------------------------------- #

def _read_linkdb(path: Path, data: CrawlData) -> None:
    # `readlinkdb -dump` prints   <target-url>\nInlinks:\n  fromUrl: <src> anchor: ...
    if not path.exists():
        return
    current: str | None = None
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            head = URL_RE.match(line)
            if head and not line.startswith(" "):
                current = head.group(0)
                data.page(current)
                continue
            if current and "fromurl" in line.lower():
                m = URL_RE.search(line)
                if m:
                    data.edge(m.group(0), current)


def _read_webgraph_dir(directory: Path, data: CrawlData, outlinks: bool) -> None:
    """Walk one of webgraph/{outlinks,inlinks}_txt and pull edges out."""
    if not directory.exists():
        return
    files = list(directory.rglob("part-*")) + list(directory.rglob("*.txt"))
    seen: set[Path] = set()
    for path in files:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        _scan_webgraph_file(path, data, outlinks=outlinks)


def _scan_webgraph_file(path: Path, data: CrawlData, *, outlinks: bool) -> None:
    current: str | None = None
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip():
                current = None
                continue
            urls = URL_RE.findall(line)
            if not urls:
                continue
            if line[:1] not in " \t":
                # Un-indented line → new node. Newer Nutch versions emit
                # "<src>\t<dst>\t<score>" on one line; handle both shapes.
                current = urls[0]
                data.page(current)
                if len(urls) >= 2:
                    other = urls[1]
                    data.edge(current, other) if outlinks else data.edge(
                        other, current)
            elif current:
                other = urls[0]
                data.edge(current, other) if outlinks else data.edge(
                    other, current)


_TITLE_RE = re.compile(r"\btitle\b\s*[:=]+\s*(.+)", re.IGNORECASE)
_URL_HEAD_RE = re.compile(r"^URL\s*[:=]+\s*(\S+)", re.IGNORECASE)
_TOURL_RE = re.compile(r"\btoUrl\b\s*[:=]+\s*(\S+)", re.IGNORECASE)


def _read_segments(root: Path, data: CrawlData) -> None:
    if not root.exists():
        return
    candidates = list(root.rglob("dump")) + list(root.rglob("part-*"))
    for path in candidates:
        if path.is_file():
            _scan_segment_file(path, data)


def _scan_segment_file(path: Path, data: CrawlData) -> None:
    current: str | None = None
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            head = _URL_HEAD_RE.match(line)
            if head:
                current = canonical(head.group(1))
                if current:
                    data.page(current)
                continue
            if not current:
                continue
            t = _TITLE_RE.search(line)
            if t:
                data.pages[current].title = t.group(1).strip()
                continue
            o = _TOURL_RE.search(line)
            if o:
                data.edge(current, o.group(1))


# ---- public entry points ------------------------------------------------- #

def read_all(dump_dir: Path) -> CrawlData:
    data = CrawlData()
    _read_linkdb(dump_dir / "linkdb.txt", data)
    _read_webgraph_dir(dump_dir / "webgraph" /
                       "outlinks_txt", data, outlinks=True)
    _read_webgraph_dir(dump_dir / "webgraph" /
                       "inlinks_txt", data, outlinks=False)
    _read_segments(dump_dir / "segments_text", data)
    return data


def restrict_to_domain(data: CrawlData, domain: str) -> CrawlData:
    domain = domain.lower().lstrip(".")
    kept = CrawlData()
    for url, page in data.pages.items():
        if registered_domain(url) == domain:
            kept.page(url, page.title)
    for src, dst in data.edges:
        if src in kept.pages and dst in kept.pages:
            kept.edges.add((src, dst))
    return kept
