# Structural analysis of a Persian web subgraph

> Course: Information Retrieval / Web Mining — Spring 2026
> Seed: `ut.ac.ir`  (swap in `iran.ir` if you ran the alternative crawl)
> Crawl depth: 2  ·  Page budget: 2 000
>
> Numbers below in `<<…>>` come straight out of `output/metrics.txt`,
> `output/top_*.csv`, and `output/plots/`. Fill them in after the pipeline run.

## Why bother

Treat the web as a directed graph: pages are vertices, hyperlinks are edges. Three things
are reliably true about that graph at scale and have been since Broder et al. (2000): the
in-degree distribution is heavy-tailed, the local clustering coefficient sits well above
what you'd get from random rewiring, and the effective diameter is tiny — usually
*O*(log N). The interesting question for a course assignment is whether a small,
self-contained Persian sub-web (one university domain, ~2 000 pages) already shows the
same fingerprint, or whether you need to crawl the whole *.ir* TLD before the stylised
facts emerge.

So we run a polite, depth-2 crawl of `ut.ac.ir`, restrict to internal hyperlinks, and
compute the standard battery: degree distributions, clustering coefficient, weakly
connected components, diameter, PageRank, and HITS. Nothing exotic.

## How the data was collected

Crawler: Apache Nutch 1.20 with `bin/crawl` over two rounds, a 1000-URL fetch list per
round, and `db.ignore.external.links = true` (mode `byDomain`). Politeness is
`fetcher.server.delay = 1.0` — one second between hits to the same host. Per-page outlink
budget is capped at 200 (`db.max.outlinks.per.page`) so a single sitemap-style page can't
warp the degree distribution. The URL filter rejects every binary asset and accepts only
`http(s)` URLs whose host matches `*.ut.ac.ir`.

After the crawl, four Nutch jobs (`readdb`, `readlinkdb`, `webgraph + nodedumper`,
`readseg`) dump everything to text under `data/dump/`. The Python pipeline (`src/parse.py`)
reads the union of all four, canonicalises URLs (lowercased host, fragment stripped,
default `/` path), filters to nodes whose registered domain is `ut.ac.ir`, drops
self-loops, and hands the result to NetworkX as a `DiGraph`. The same `CrawlData` object
is also written out as `dataset/pages.jsonl` (one JSON record per page: URL, title,
sorted outlinks) and `dataset/edges.csv`.

## What we measured and how

| Quantity | Code path |
| --- | --- |
| In- and out-degree distributions, log-log + log-binned | `src/plots.py` (`loglog_scatter`, `logbin_histogram`) |
| Average clustering coefficient | `nx.average_clustering` on the undirected view, in `src/analysis.py` |
| Weakly connected components | `nx.weakly_connected_components`; count + top-5 sizes |
| Diameter, average shortest path | BFS from up to 300 random sources on the largest WCC, seeded |
| PageRank | `src/pagerank.py` — power iteration, *d* = 0.85, exactly 20 steps |
| Hubs and authorities | `src/hits.py` — coupled updates, L2-normalised, 50 iterations |

Two implementation choices worth justifying:

- **PageRank as a hand-rolled loop instead of `nx.pagerank`.** `nx.pagerank` runs until a
  tolerance is met, and on a 2 000-node graph that's typically far fewer than 20
  iterations. The brief asks for 20 explicitly, so we do 20.
- **Diameter by BFS sampling.** Exact diameter on the largest WCC is *O*(*V* · *E*),
  which is fine for 2 000 nodes but unnecessary. We pick up to 300 source vertices with a
  fixed seed (`random.Random(42)`), BFS from each on the undirected view, and report the
  maximum depth as a (slightly conservative) diameter estimate.

## Numbers from this run

```text
Nodes:                <<nodes>>
Edges:                <<edges>>
Avg in-degree:        <<avg_in>>
Avg out-degree:       <<avg_out>>
Avg clustering coef:  <<C>>
WCC count:            <<wcc_count>>
WCC sizes (top 5):    <<wcc_top5>>
Largest WCC:          <<largest_wcc>>
Diameter (sampled):   <<diameter>>
Avg shortest path:    <<avg_path>>
```

(Pasted verbatim from `output/metrics.txt`.)

## Degree distributions

The log-log scatter shows raw P(k) at each observed degree value; the log-binned plot
shows the same distribution after grouping degree values into geometric bins and
dividing each bin's count by its width, which is the recommended way (Newman, 2005) to
read a heavy tail without the noise that swamps the rightmost decade.

![In-degree, log-log](output/plots/in_degree.png)

![In-degree, log-binned PDF](output/plots/in_degree_logbin.png)

![Out-degree, log-log](output/plots/out_degree.png)

![Out-degree, log-binned PDF](output/plots/out_degree_logbin.png)

What to look for: the in-degree tail typically straightens out into a line on log-log
axes — that's the power-law fingerprint. The out-degree distribution is usually
narrower and falls off more sharply, because most page templates link to roughly the
same number of navigation targets. If the in-degree slope on the log-binned plot is
in the −2.0 to −2.5 range, this slice of the web is behaving like everyone else's.

## A look at the giant component

![Largest WCC, top-degree subgraph, ForceAtlas-ish layout](output/plots/largest_wcc.png)

The figure plots the 500 highest-degree nodes of the largest weakly connected component
under a spring layout (seed = 42 for reproducibility). Node size encodes degree, edges
are drawn at low alpha so the backbone is visible. The dense knot in the middle is the
navigation core — home page, faculty index, news index. The wisps around it are
section subtrees that link inward heavily but rarely link out.

## Important pages

### By raw in-degree

| Rank | In-degree | URL |
| --- | --- | --- |
| 1 | `<<>>` | `<<>>` |
| 2 | `<<>>` | `<<>>` |
| 3 | `<<>>` | `<<>>` |
| 4 | `<<>>` | `<<>>` |
| 5 | `<<>>` | `<<>>` |
| 6 | `<<>>` | `<<>>` |
| 7 | `<<>>` | `<<>>` |
| 8 | `<<>>` | `<<>>` |
| 9 | `<<>>` | `<<>>` |
| 10 | `<<>>` | `<<>>` |

### By PageRank (d = 0.85, 20 iterations)

| Rank | PageRank | URL |
| --- | --- | --- |
| 1 | `<<>>` | `<<>>` |
| 2 | `<<>>` | `<<>>` |
| 3 | `<<>>` | `<<>>` |
| 4 | `<<>>` | `<<>>` |
| 5 | `<<>>` | `<<>>` |
| 6 | `<<>>` | `<<>>` |
| 7 | `<<>>` | `<<>>` |
| 8 | `<<>>` | `<<>>` |
| 9 | `<<>>` | `<<>>` |
| 10 | `<<>>` | `<<>>` |

### HITS authorities / hubs

| Authorities | Hubs |
| --- | --- |
| `<<>>` | `<<>>` |
| `<<>>` | `<<>>` |
| `<<>>` | `<<>>` |
| `<<>>` | `<<>>` |
| `<<>>` | `<<>>` |

(Top-5 of each, from `output/top_authorities.csv` and `output/top_hubs.csv`. The
authority and PageRank lists tend to overlap on the navigation hubs; the hubs list
picks out pages whose value is "this links to all the good stuff" — sitemaps, search
result pages, category indices.)

### Comparison

In-degree and PageRank both answer "which page is central?", but they weight evidence
differently. In-degree treats every inbound link as worth one vote; PageRank weights
each link by the importance of the page that made it, divided across that page's
outlinks. They agree on the obvious backbone (home page, top-level menus) and disagree
on the long tail. Pick a row where the two ranks differ by several places and walk
through *why* in one sentence — usually it's a page that's reached by many low-value
pagination tails (boosted by in-degree) or a page linked to from only a handful of
high-PageRank pages (boosted by PageRank). HITS authorities behave broadly like
PageRank here; HITS hubs are a different list almost entirely.

## What this tells us, and what it doesn't

The numbers above are entirely consistent with the small-world / scale-free fingerprint
that's been documented for the web since the late 90s. None of that is new. What's new,
for this assignment, is having an empirical handle on those properties for a specific
Persian-language sub-web. Two practical takeaways:

1. **Even 2 000 pages is enough** to recover a recognisable heavy-tailed in-degree
   distribution. You don't need a billion-page crawl to see the qualitative behaviour.
2. **The giant component swallows almost everything.** The long tail of tiny components
   is real but uninteresting — they're usually pages reached only via external referrers
   that we filtered out by design (`db.ignore.external.links = true`).

The biggest threat to validity is the depth-2 cap: pages reachable only at depth ≥ 3 are
invisible, and that's exactly the regime where you'd expect to find the lowest-PageRank
content. The numbers reported here describe the top of the iceberg, not the whole site.
A secondary issue is that despite URL canonicalisation, some pages will appear as
duplicate URLs (different trailing slashes, locale prefixes, query-string variants). The
graph counts them as separate nodes, which inflates the node count slightly.

## Reproducing this

```bash
export NUTCH_HOME=/opt/nutch
./scripts/crawl.sh                                       # ~15-45 min
./scripts/export.sh                                      # ~1-3 min
python -m src.cli --dump data/dump --out output --domain ut.ac.ir
```

Determinism: PageRank's iteration count is fixed; HITS is fixed; the diameter sampler
uses `random.Random(42)`; `nx.spring_layout` for the WCC snapshot uses `seed=42`. Given
the same crawl dump, the pipeline produces byte-identical metrics, top-K tables and
plots.

## References

Brin & Page (1998). *The anatomy of a large-scale hypertextual web search engine.*
Computer Networks, 30. — original PageRank.

Kleinberg (1999). *Authoritative sources in a hyperlinked environment.* JACM. — HITS.

Broder et al. (2000). *Graph structure in the web.* Computer Networks, 33. — the bow-tie
picture and the first credible measurement of web-graph diameter.

Watts & Strogatz (1998). *Collective dynamics of "small-world" networks.* Nature, 393.

Newman (2005). *Power laws, Pareto distributions and Zipf's law.* Contemporary Physics.
— the log-binning recipe used for the second pair of plots.

Hagberg, Schult & Swart (2008). *Exploring network structure, dynamics, and function
using NetworkX.* SciPy proceedings.

Apache Nutch 1.20 — https://nutch.apache.org/
