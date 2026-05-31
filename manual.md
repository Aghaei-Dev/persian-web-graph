# How to run this project

The work splits into two halves: Nutch crawls a Persian domain and dumps the link
structure, then a small Python pipeline turns those dumps into a directed graph and
computes every metric the brief asks for.

If you just want the cheat sheet, jump to the end.

## What you need installed

Java 11 or 17 (Nutch 1.22 runs on both — `java -version` should print something), Python
3.10+, and roughly 1 GB of free disk for the crawl artefacts. The Python side only depends
on `networkx` and `matplotlib`; everything else is stdlib.

Grab Nutch 1.22 from the Apache archive and untar it somewhere you'll remember:

```bash
cd /opt
wget https://dlcdn.apache.org/nutch/1.22/apache-nutch-1.22-bin.tar.gz
tar xzf apache-nutch-1.22-bin.tar.gz
mv apache-nutch-1.22 nutch
```

Then point `NUTCH_HOME` at it (add this to `~/.bashrc` so future shells inherit it):

```bash
export NUTCH_HOME=/opt/nutch
```

`"$NUTCH_HOME/bin/nutch" -help` should print the sub-command list. If it complains about
`JAVA_HOME`, set that too:

```bash
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
```

also add them in zsh if you have

```bash
nano ~/.zshrc
```

then

```bash
# nutch
export NUTCH_HOME=/opt/nutch

# java
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))

```

## Picking the seed

Two files together decide which domain Nutch crawls:

- `nutch/urls/seed.txt` — the starting URL, one per line. The default is
  `https://www.sharif.ir/`. Replace it with `https://www.iran.ir/` if you want to run the
  other variant.
- `nutch/conf/regex-urlfilter.txt` — the accept rule at the bottom. By default it accepts
  anything under `*.sharif.ir`. If you switched seed, also change this line:

  ```text
  +^https?://([a-z0-9-]+\.)*ut\.ac\.ir(/|$)
  ```

  to

  ```text
  +^https?://([a-z0-9-]+\.)*iran\.ir(/|$)
  ```

The accept rule has to match the seed or Nutch will fetch the home page once, find no URL
it's allowed to follow, and stop with zero edges. (This is the single most common way for
a Nutch crawl to silently "succeed" with no data.)

You don't need to copy these files into the Nutch install — `scripts/crawl.sh` does that
for you every run.

## Running the crawl

From the project directory:

```bash
./scripts/crawl.sh
```

That runs Nutch's bundled `bin/crawl` script for two rounds with a 1000-URL fetch list per
round, which lands at most ~2000 fetched pages — the cap the assignment asks for. Wall
time on a normal connection is in the 15–45 minute range; most of it is the 1-second
politeness delay between requests to the same host (`fetcher.server.delay = 1.0` in
`nutch-site.xml`).

What gets left behind: `data/crawl/{crawldb,linkdb,segments}/`. None of these are text
files — they're Hadoop SequenceFiles, hence the next step.

If the run ends with zero fetched pages, the culprit is almost always the URL filter, the
seed, or `robots.txt`. Try `curl -I https://www.sharif.ir/` to make sure the host is even
reachable.

## Pulling out the dumps

```bash
./scripts/export.sh
```

This runs four Nutch sub-commands and lands plain text under `data/dump/`:

- `crawldb.txt` — per-URL status from `readdb`.
- `linkdb.txt` — inbound links per URL from `readlinkdb`.
- `webgraph/{outlinks,inlinks,scores}_txt/` — the canonical structural artefacts, produced
  by Nutch's `webgraph` + `nodedumper` jobs.
- `segments_text/<segment>/dump` — `readseg` output, with page titles and outlinks.

The Python pipeline takes the union of all four. If one of them is missing or in a
slightly different format (Nutch's text dumps shift between point releases), the parser
just skips it; the others usually carry enough signal on their own.

## The Python side

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then:

```bash
python -m src.cli --dump data/dump --out output --domain sharif.ir
```

(`--domain iran.ir` if you crawled the other site.)

The CLI prints a short log and a final one-line summary like:

```text
N=1873  E=42117  <k_in>=22.486  C=0.184  WCCs=6  diam~14
```

…and writes everything else under `output/`:

```text
output/
├── webgraph.graphml          full directed graph
├── webgraph.gexf             same graph, GEXF (Gephi opens this directly)
├── metrics.txt               flat key:value report
├── top_in_degree.csv         top-10 by raw in-degree
├── top_out_degree.csv        top-10 by raw out-degree
├── top_pagerank.csv          top-10 by PageRank (d=0.85, 20 iters)
├── top_authorities.csv       top-10 HITS authorities
├── top_hubs.csv              top-10 HITS hubs
├── pagerank_all.csv          PageRank for every node, sorted desc
├── dataset/
│   ├── pages.jsonl           one record per page: {url, title, outlinks}
│   └── edges.csv             flat (src, dst) edge list
└── plots/
    ├── in_degree.png         log-log scatter
    ├── out_degree.png        log-log scatter
    ├── in_degree_logbin.png  log-binned PDF (Newman style)
    ├── out_degree_logbin.png log-binned PDF
    └── largest_wcc.png       force-directed sketch of the giant component
```

`dataset/pages.jsonl` is the "crawl dataset of ≥2000 pages and their links" the brief
asks for as its own deliverable.

## What runs where in the code

- `src/parse.py` — reads all four Nutch dump shapes into a `CrawlData` (pages + edges).
  Permissive: tries to grab a URL out of any line in the right place.
- `src/graph.py` — `CrawlData` → `networkx.DiGraph`, plus GraphML/GEXF writers and a
  largest-WCC helper.
- `src/pagerank.py` — power iteration, `d = 0.85`, fixed 20 iterations, dangling mass
  redistributed uniformly. Hand-rolled rather than `nx.pagerank` so the iteration count
  matches the brief exactly.
- `src/hits.py` — same idea for HITS. Two coupled updates per iteration, L2-normalise,
  repeat.
- `src/analysis.py` — degree stats, clustering coefficient (on the undirected view),
  weakly connected components, BFS-sampled diameter, and the CSV writers for every top-K
  table.
- `src/dataset.py` — `pages.jsonl` and `edges.csv` writers.
- `src/plots.py` — log-log scatter, log-binned PDF (geometric bins, divided by bin width),
  and the WCC snapshot.
- `src/cli.py` — glues all of the above together.

## Gephi (optional)

`webgraph.gexf` opens straight in Gephi. ForceAtlas 2 for layout, colour by PageRank,
size by in-degree — that's the screenshot most people put in the report.

## Switching to iran.ir mid-stream

1. Edit `nutch/urls/seed.txt` and `nutch/conf/regex-urlfilter.txt` as above.
2. Wipe the old crawl: `rm -rf data/crawl data/dump`.
3. `./scripts/crawl.sh && ./scripts/export.sh`.
4. `python -m src.cli --dump data/dump --out output_iran --domain iran.ir`.

## When things go wrong

- **Zero fetched pages.** URL filter doesn't match the seed, or `robots.txt` blocks the
  path. Check both. Don't bypass robots.
- **Crawl runs but `data/dump/webgraph` is empty.** `bin/nutch webgraph` needs at least
  one segment with parsed data; if the first round failed to parse anything, the WebGraph
  job has nothing to chew on. Re-run with `--num-fetchers 1` and watch the parse phase.
- **Pipeline prints "0 nodes after restricting to sharif.ir".** Your dump contains URLs but
  none with `sharif.ir` as registered domain. Either the seed was wrong or you passed the
  wrong `--domain` flag.
- **Diameter is reported as `None`.** The largest WCC is a singleton — almost certainly
  means the parser found nodes but no edges. Check `data/dump/webgraph/outlinks_txt/` has
  non-empty `part-*` files.

## Cheat sheet

```bash
export NUTCH_HOME=/opt/nutch
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

./scripts/crawl.sh                                       # ~15-45 min
./scripts/export.sh                                      # ~1-3 min
python -m src.cli --dump data/dump --out output --domain sharif.ir
```

Then open `output/metrics.txt`, `output/plots/*.png`, and the `top_*.csv` files. Numbers
and figures from there feed straight into `report.md`.
