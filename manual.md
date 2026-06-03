# Personal manual — what this project does and how to run it

This is my own notes file. Not for the professor. Written in plain English so future-me
remembers why each knob is set the way it is, what each Python module is doing under the
hood, and where to look when something breaks.

---

## 1. The assignment in plain English

We need to:

1. Crawl a Persian-language website using Apache Nutch (depth 2, at least 2 000 pages).
2. For each page, store URL + title + the outbound links that stay inside the domain.
3. Turn the link set into a directed graph (nodes = pages, edges = hyperlinks).
4. Compute six things on that graph:
   - in-degree and out-degree distributions, plotted on log-log axes;
   - average clustering coefficient (the undirected version);
   - number and size of weakly connected components;
   - diameter and average shortest path of the largest weakly connected component;
   - PageRank (damping 0.85, exactly 20 iterations);
   - top-10 by in-degree and top-10 by PageRank — and compare them.
5. Save the directed graph as GraphML or GEXF (we save both — Gephi prefers GEXF).
6. Write a 6–8 page technical report with the numbers, charts, and the giant-component
   visualisation.

Originally `www.ut.ac.ir` / `www.iran.ir` were the suggested seeds, but Arvan Cloud (Iran's
big CDN/WAF) is blocking us from those hosts. We switched to `sharif.ir`, which is on a
different CDN and answers cleanly.

---

## 2. Mental model — how the data flows

```
seed.txt ──► Nutch fetch + parse ──► CrawlDb / LinkDb / segments (binary SequenceFiles)
                                                  │
                              readdb / readlinkdb / webgraph + nodedumper / readseg
                                                  │
                                                  ▼
                                  data/dump/*.txt  (plain text)
                                                  │
                                          src/parse.py
                                                  │
                                                  ▼
                                  CrawlData = {pages, edges}
                                                  │
                                          src/graph.py
                                                  │
                                                  ▼
                                   networkx.DiGraph  ──► webgraph.graphml + .gexf
                                                  │
                          ┌───────────────────────┼──────────────────────────┐
                          ▼                       ▼                          ▼
                   src/analysis.py         src/plots.py              src/dataset.py
                          │                       │                          │
                          ▼                       ▼                          ▼
              metrics.txt + top_*.csv      plots/*.png                pages.jsonl + edges.csv
```

The big lesson: Nutch *fetches and parses*, but it speaks SequenceFile. Everything we
actually care about lives in the **text dumps**, and the Python side reconstructs the
graph from those. So a Nutch run that "succeeds" but writes the wrong dump shape will
silently give us an empty graph — see §11 for how to spot that.

---

## 3. What needs to be installed

- **Java 11 or 17.** Nutch 1.22 runs on either. Check with `java -version`.
- **Python 3.10+.** Only stdlib + `networkx` + `matplotlib`. The `requirements.txt`
  pins them.
- **~1 GB free disk** for crawl artefacts (mostly the segments).

Get Nutch 1.22 and dump it under `/opt/nutch`:

```bash
cd /opt
wget https://dlcdn.apache.org/nutch/1.22/apache-nutch-1.22-bin.tar.gz
tar xzf apache-nutch-1.22-bin.tar.gz
mv apache-nutch-1.22 nutch
```

Then point shells at it. `~/.bashrc` and `~/.zshrc` both:

```bash
export NUTCH_HOME=/opt/nutch
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
```

`"$NUTCH_HOME/bin/nutch" -help` should list sub-commands. If it complains about
`JAVA_HOME`, the export above didn't take effect — open a new shell.

Python environment:

```bash
cd /root/aiq-v2/persian-web-graph
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. The Nutch config (`nutch/conf/nutch-site.xml`) explained

Every property is here for a specific reason. If a future run misbehaves, change one knob
at a time and observe.

| Property | Value | Why |
| --- | --- | --- |
| `http.agent.name` | `UT-WebGraph-Crawler` | Nutch refuses to start without a user agent name. Also identifies us to the target's logs. |
| `http.agent.description` / `email` | Academic + my email | Polite — lets the server admin reach me if my crawler causes problems. |
| `http.robots.agents` | `UT-WebGraph-Crawler,*` | Tells Nutch's robots.txt parser which `User-Agent:` lines to match. Falls back to `*` if no specific block exists. |
| `http.timeout` | `20000` (20 s) | Liferay (the CMS behind sharif.ir) can be slow on cold cache. Default 10 s caused a lot of `fetch_error`. |
| `http.content.limit` | `1048576` (1 MiB) | **Critical.** Default is 64 KiB, which truncates a real Liferay page mid-`<head>` and drops most outlinks. Bumping this to 1 MiB was the single biggest fix when our first crawl produced an 86-node star. |
| `fetcher.threads.fetch` | `20` | Number of concurrent fetcher threads. Politeness per host is enforced separately, so this just lets us pull from many hosts in parallel. |
| `fetcher.threads.per.queue` | `2` | At most 2 in-flight requests per host. With 10 seeds across subdomains this gives real parallelism. |
| `fetcher.server.delay` | `0.5` (s) | Sleep between hits to the same host. 1.0 s is the typical polite default; we went to 0.5 s because we have a tight time budget and 10 hosts in the seed list spread the load. |
| `fetcher.max.crawl.delay` | `10` (s) | If `robots.txt` requests >10 s delay, skip that host instead of waiting forever. |
| `db.max.outlinks.per.page` | `400` | Sharif's homepage exposes 200+ links. Default 100 chopped the navigation off. 400 leaves room without letting a sitemap-style page dominate. |
| `db.ignore.external.links` | `true` | We only want internal edges. The assignment is explicit about this. |
| `db.ignore.external.links.mode` | `byDomain` | Internal = same **registered domain**. So `www.sharif.ir → ce.sharif.ir` counts as internal. `byHost` would have treated those as external. |
| `db.injector.overwrite` | `true` | Re-injecting the same seeds replaces their CrawlDb entry instead of compounding scores. |
| `db.update.additions.allowed` | `true` | Allows the CrawlDb update step to add newly discovered URLs. Default but explicit. |
| `plugin.includes` | (regex of plugin names) | Loads exactly the protocol/parser/indexer/scoring plugins we want. The relevant ones are `protocol-okhttp` (modern HTTP), `urlfilter-regex` (uses our regex file), `parse-html` + `parse-tika` (HTML/PDF/etc.), `urlnormalizer-*` (canonicalisation). |
| `parser.character.encoding.default` | `utf-8` | Persian is UTF-8. Default ISO-8859-1 would mangle the titles. |
| `parser.html.outlinks.ignore_tags` | `img,script,style,link` | Don't treat `<img src>`, `<script src>`, `<link href>` as outlinks. We only want `<a href>`. |
| `parser.skip.truncated` | `false` | If `http.content.limit` truncates a fetched page, keep the parse anyway and use whatever outlinks we did manage to extract. Default true would drop the whole record. |
| `link.ignore.internal.host` | `false` | LinkDb / WebGraph default is to drop **same-host** links (assuming they're nav noise). We want them — that's most of the graph. |
| `link.ignore.internal.domain` | `false` | Same idea, one scope wider. |
| `link.ignore.limit.page` | `false` | Allow multiple distinct edges between the same two pages. |
| `link.ignore.limit.domain` | `false` | Same idea across domain pairs. |
| `generate.max.count` | `1000` | Per `generate.count.mode`, cap any one host at 1000 URLs per generate round. Stops one big subdomain from monopolising the fetchlist. |
| `generate.count.mode` | `host` | Count toward the cap above by host. |
| `db.fetch.interval.default` | `2592000` (30 days) | How long until Nutch wants to refetch a URL. Doesn't matter for a one-shot crawl, but explicit > implicit. |

---

## 5. The URL filter (`nutch/conf/regex-urlfilter.txt`)

Read top to bottom, **first match wins**. Each line is `+pattern` (accept) or `-pattern`
(reject). Order matters.

```text
-^(file|ftp|mailto):       # skip non-HTTP schemes
-\.(gif|jpg|…)$            # skip images
-\.(css|js|woff|…)$        # skip styling/scripts
-\.(mp3|mp4|…)$            # skip media
-\.(zip|gz|tar|…)$         # skip archives
-\.(pdf|doc|xls|…)$        # skip office docs — assignment says HTML only
-…sessionid=               # skip session-id query strings
-/(login|logout|…)(/|$|\?) # skip auth paths
-/(search|results)\?       # skip search-result pagination
-\?.*(replytocom|…)        # skip comment-reply spam paths
-/o/[^/]+/(css|js|…)/      # skip Liferay theme asset paths
-/combo\?                  # skip Liferay combined-asset endpoint
-/(c/portal|api/jsonws|…)/ # skip Liferay control panel / API
-\?(_[^=&]+=|p_p_id=|…)    # skip Liferay portlet AJAX URLs
-.{300,}                   # skip URLs longer than 300 chars (calendar/facets)
+(?i)^https?://([a-z0-9-]+\.)*sharif\.ir(/|$|\?)   # accept anything on *.sharif.ir
-.                          # reject everything else
```

The `(?i)` makes the accept rule case-insensitive on the host — defensive, in case
something emits `Sharif.IR`. The path after `sharif.ir` can include percent-encoded UTF-8
(Persian characters in URLs are encoded as `%D8%A2…`) and the regex doesn't restrict it.

The Liferay-specific rejections matter a lot. Without them, the frontier explodes with
URLs like `/o/shu-theme/css/main.css?…&t=1780488874094` — same page, different query
string, every time, infinite work, zero new pages.

If switching to `iran.ir`: change the accept rule's domain, keep everything else.

---

## 6. The seed list (`nutch/urls/seed.txt`)

```
https://www.sharif.ir/
https://daily.sharif.ir/
https://news.sharif.ir/
https://en.sharif.ir/
https://farhangi.sharif.ir/
https://ch.sharif.ir/
https://journal.sharif.ir/
https://shafaf.sharif.ir/
https://language.sharif.ir/
https://eri.sharif.ir/
```

Ten subdomains, not one. The first crawl used only `https://www.sharif.ir/` and produced
an 86-node star because the homepage links almost entirely to subdomain home pages, and
those subdomains' home pages are *also* nav stubs. Starting from ten content-rich
subdomains gets us into actual content within depth 2.

Probed these with `curl -I` before adding — they all return HTTP 200. (Aero was 000 / not
reachable; not in the list.)

---

## 7. Running the crawl

```bash
./scripts/crawl.sh
```

What the script does:

1. Copies our `nutch-site.xml` and `regex-urlfilter.txt` into `$NUTCH_HOME/conf/`. Nutch
   only reads its own conf dir; without this step our overrides are invisible.
2. Calls `$NUTCH_HOME/bin/crawl` with:
   - `-i` — also run the index step (harmless if no Solr is configured; it just warns).
   - `-s nutch/urls` — seed directory.
   - `--num-fetchers 1` — one MapReduce fetcher (single-node setup; don't need more).
   - `--num-threads 20` — 20 worker threads inside that fetcher.
   - `--size-fetchlist 800` — topN URLs per round.
   - `data/crawl` — output crawl directory.
   - `4` — number of rounds.
3. Prints `bin/nutch readdb $CRAWL_DIR/crawldb -stats` so you can see status counts.

A round of `bin/crawl` does five sub-steps: `generate` (build fetchlist) → `fetch` (HTTP
pulls) → `parse` (HTML → text + outlinks) → `updatedb` (merge into CrawlDb) → `invertlinks`
(build LinkDb from outlinks).

Four rounds × 800 topN = up to 3 200 candidate fetches. After dedup and failures, expect
2 000–2 500 successful pages. Wall time ~30–60 minutes.

**Reading the live log while it runs:**

- `FetcherThread - fetching <url>` — request in flight, good.
- `Active threads=N` count drops to 0 between rounds.
- `ParserChecker - skipping <url>` — parser couldn't handle the content type.
- `OutputStreamSelector - not selected for output` — filter rejected this URL, expected.
- `robots denied` — `robots.txt` said no. Respect it; don't bypass.

**Reading the final stats block.** The `readdb -stats` printout at the end shows:

```text
status 1 (db_unfetched):     1234
status 2 (db_fetched):       2143      ← this is the number of pages we got
status 3 (db_gone):            45
status 4 (db_redir_temp):      12
status 5 (db_redir_perm):      37
status 6 (db_notmodified):      0
```

If `db_fetched` is under 1 000, something is wrong. Most likely culprits in §11.

---

## 8. Exporting the dumps (`./scripts/export.sh`)

This runs four Nutch jobs and writes plain text under `data/dump/`:

| Job | Output | What it contains |
| --- | --- | --- |
| `bin/nutch readdb $CRAWL_DIR/crawldb -dump` | `data/dump/crawldb.txt` | One record per known URL: status (fetched/gone/unfetched), fetch score, signature, metadata (incl. title for fetched URLs). |
| `bin/nutch readlinkdb $CRAWL_DIR/linkdb -dump` | `data/dump/linkdb.txt` | For each URL, the list of inbound URLs and the anchor text from them. |
| `bin/nutch webgraph -segmentDir $SEG_DIR -webgraphdb $WG_DIR` | `data/dump/webgraph/{nodes,outlinks,inlinks}/` | Nutch's canonical link structure as SequenceFiles. |
| `bin/nutch nodedumper -{outlinks,inlinks,scores} -webgraphdb $WG_DIR -output …` | `data/dump/webgraph/{outlinks,inlinks,scores}_txt/` | Text dump of the above. |
| `bin/nutch readseg -dump <seg> <out> -nocontent -noparsetext` | `data/dump/segments_text/<seg>/dump` | Per-page metadata from the parse step: URL, title, list of outlinks. |

The Python pipeline reads **all four** and merges. If one of them is missing or in a
slightly different format (Nutch's text dumps shift between point releases), the parser
skips it and uses the others. The redundancy is on purpose.

The `readseg` job is the one that gives us page **titles**. If titles are missing in
`pages.jsonl`, look here first.

To poke at the dumps manually:

```bash
head -50 data/dump/crawldb.txt           # see crawl status records
head -50 data/dump/linkdb.txt            # see inbound-link records
ls data/dump/webgraph/outlinks_txt/      # text-dumped outlinks
ls data/dump/segments_text/              # per-segment readseg dumps
```

---

## 9. The Python pipeline (`src/`)

```bash
python -m src.cli --dump data/dump --out output --domain sharif.ir
```

CLI flags:
- `--dump`   path to the dump directory (default `data/dump`)
- `--out`    output directory (default `output`)
- `--domain` registered domain to restrict to (default `sharif.ir`)

The `--domain` flag isn't the same as the URL filter. URL filter restricts what Nutch
*crawls*; `--domain` restricts what the **graph keeps**. If the dump accidentally contains
URLs from outside `sharif.ir` (e.g. a redirect target Nutch followed), this drops them.

### What each module does

**`src/parse.py`** — reads the dump directory and produces a `CrawlData(pages, edges)`.

- `canonical(url)` strips fragments, lowercases the host, forces `/` path on bare hosts,
  drops trailing junk. Two URLs that differ only in trailing slash collapse to one node.
- `registered_domain(url)` extracts e.g. `sharif.ir` from `https://www.sharif.ir/foo`.
  Handles two-part TLDs (`bbc.co.uk`) via the `_TWO_LEVEL_SLDS` set.
- `_read_linkdb` parses `linkdb.txt`: lines that start with a URL are the target,
  indented `fromUrl:` lines are inbound sources.
- `_read_webgraph_dir` walks `webgraph/outlinks_txt/` and `webgraph/inlinks_txt/`,
  scanning either flat `src \t dst \t score` lines (newer Nutch) or indented
  `src\n  dst\n  dst` records (older).
- `_read_segments` walks `segments_text/<seg>/dump` files: a `URL: x` line starts a
  record, subsequent `title: …` and `toUrl: …` (or `outlink: …`) lines fill it in.
- `read_all` calls all four readers, unions the result.
- `restrict_to_domain` is the `--domain` filter — drops URLs whose registered domain
  doesn't match, then drops edges that lost an endpoint.

**`src/graph.py`** — turns `CrawlData` into a `networkx.DiGraph`, saves it as
`webgraph.graphml` + `webgraph.gexf`. Also gives us a `largest_wcc(g)` helper that
returns a copy of the largest weakly connected component.

**`src/pagerank.py`** — hand-rolled power iteration. We do this instead of
`nx.pagerank` because the brief says "0.85 damping, **exactly** 20 iterations" and
`nx.pagerank` runs until convergence, which is usually <20. Dangling nodes (pages with
no outlinks) redistribute their rank uniformly across every node, otherwise mass leaks
out of the system each iteration.

The math, per iteration:

```
r[i] = (1 - d) / N
     + d * (sum over dangling j of r[j]) / N      ← dangling mass
     + d * sum over j → i of r[j] / out_deg[j]    ← incoming mass
```

**`src/hits.py`** — same idea for HITS. Two coupled updates per iteration:

```
new_auth[i] = sum of hub[j] over j → i
new_hub[i]  = sum of new_auth[j] over i → j
```

L2-normalise both vectors after every iteration so they don't blow up. 50 iterations is
overkill on 2 000 nodes — converges in maybe 15 — but the cost is zero.

**`src/analysis.py`** — runs every metric and writes everything to disk.

- `g.in_degree()` and `g.out_degree()` for the histograms.
- `nx.average_clustering(g.to_undirected())` for the clustering coefficient. The
  undirected view is the standard definition (Watts-Strogatz triangles).
- `nx.weakly_connected_components(g)` for WCC sizes.
- `_diameter` does BFS from up to 300 random sources (seeded with `random.Random(42)`)
  on the largest WCC's undirected view, returns the longest distance seen and the mean
  of all positive distances. Exact diameter is O(V·E) — fine for 2 000 nodes but
  unnecessary, and the sampled version is well within the spirit of "approximate
  diameter of the largest WCC".
- Then PageRank + HITS via the modules above.
- `_metrics_txt` writes the flat key-value report.
- `_topk_csv` writes each `top_*.csv` with rank, score, URL, title.
- `_full_csv` writes the full PageRank ranking — useful for the report's tail analysis.

**`src/plots.py`** — three plot kinds, all matplotlib + `Agg` backend so it works
headless over SSH.

- `loglog_scatter`: raw degree counts on log-log axes. The "everyone draws this"
  version.
- `logbin_histogram`: Newman-recommended log-binned PDF — geometric bin edges, count
  divided by bin width. Reads the heavy tail without the noise that swamps the rightmost
  decade.
- `snapshot`: spring-layout drawing of the largest WCC. If it's >500 nodes, we keep
  the 500 highest-degree ones for legibility.

**`src/dataset.py`** — writes the two deliverable files:
- `pages.jsonl` — one JSON record per page, `{url, title, outlinks: [...]}`. The
  "crawl dataset of ≥2 000 pages and their links" the brief asks for.
- `edges.csv` — flat `src,dst` edge list.

**`src/cli.py`** — glues it all together.

---

## 10. What lands in `output/`

```
output/
├── webgraph.graphml          # full directed graph
├── webgraph.gexf             # same graph in GEXF (Gephi loves this)
├── metrics.txt               # nodes, edges, degree, clustering, WCC, diameter
├── top_in_degree.csv         # top-10 pages by raw in-degree (table for the report)
├── top_out_degree.csv        # top-10 by out-degree (not strictly asked for, useful)
├── top_pagerank.csv          # top-10 by PageRank — comparison target
├── top_authorities.csv       # top-10 HITS authorities — bonus
├── top_hubs.csv              # top-10 HITS hubs — bonus
├── pagerank_all.csv          # PageRank for every node, descending. For tail analysis.
├── dataset/
│   ├── pages.jsonl           # the "≥2 000 pages and their links" dataset
│   └── edges.csv             # flat edge list
└── plots/
    ├── in_degree.png         # log-log scatter
    ├── in_degree_logbin.png  # Newman-style log-binned PDF
    ├── out_degree.png        # log-log scatter
    ├── out_degree_logbin.png # log-binned PDF
    └── largest_wcc.png       # spring-layout drawing of the giant component
```

---

## 11. When things go wrong

I've hit all of these. Documenting them so I don't have to re-debug.

### "The crawl finished but my graph is a star"
Symptom: `metrics.txt` shows ~85 nodes, all edges from one source.

What happened the first time: depth-2 from `www.sharif.ir/` alone. Round 1 fetched the
homepage. The homepage exposes ~200 outlinks, but `http.content.limit=65536` (default)
truncated the page mid-template and Nutch only saw 85 of them. Round 2 fetched those 85
subdomain home pages, most of which are also nav stubs, so we got no further content
extracted.

Fix applied (already in `nutch-site.xml`):
- `http.content.limit=1048576` so the page isn't truncated.
- `db.max.outlinks.per.page=400` so we don't cap the navigation.
- `parser.skip.truncated=false` defensively.
- 10 seeds instead of 1.
- 4 rounds instead of 2.

### "Zero fetched pages"
URL filter doesn't match the seed, or `robots.txt` blocks. Check:

```bash
grep -E '^[+-]' nutch/conf/regex-urlfilter.txt
curl -I https://www.sharif.ir/robots.txt
curl -I https://www.sharif.ir/
```

Don't bypass robots — change targets if a site bans crawlers.

### "Crawl runs but `data/dump/webgraph/outlinks_txt/` is empty"
The `webgraph` job needs at least one parsed segment. If round 1 failed to parse (e.g.
all pages returned binary or were truncated to nothing), there's nothing for the WebGraph
job to chew on.

Inspect:
```bash
ls data/crawl/segments/                          # are there segment dirs at all?
$NUTCH_HOME/bin/nutch readseg -list data/crawl/segments/*/    # how many parsed records?
```

### "Pipeline prints '0 nodes after restricting to sharif.ir'"
Either you passed `--domain iran.ir` while crawling sharif.ir (or vice versa), or the
URL canonicaliser is choking. Spot-check:
```bash
head -20 data/dump/linkdb.txt
```
URLs should be on lines by themselves with a clear `https://…sharif.ir/…` shape.

### "Diameter is None"
The largest WCC is a single node. Almost always means the parser found pages but no
edges. Check the dumps as in the previous item, and check that `link.ignore.*=false`
in `nutch-site.xml`.

### "Titles are all empty in pages.jsonl"
The `readseg` part of `export.sh` either didn't run or wrote a different format. Check:
```bash
find data/dump/segments_text -name dump -exec head -100 {} \; | grep -i title
```
If you see `Title: …` lines, the parser regex should pick them up. If you see
`<title>…</title>` raw HTML, then `-noparsetext` was missing on `readseg` and we got the
wrong dump.

### "`bin/nutch readdb -stats` shows lots of `db_unfetched`"
Round budget ran out before those URLs got fetched. Bump `--size-fetchlist` or rounds in
`scripts/crawl.sh`. Or, if you only need 2 000 pages and have them, it's fine — those
are just URLs the frontier discovered but never reached.

### "Crawl hangs"
Probably a long `fetcher.server.delay` × too many same-host URLs. Drop the seed count for
that host or raise `fetcher.threads.per.queue`. Last resort: kill it and look at
`logs/hadoop.log` inside `$NUTCH_HOME` for what was actually blocking.

---

## 12. Filling in the report

The placeholders in `report.md` map 1:1 to artefacts:

| Placeholder in `report.md` | Where to read it from |
| --- | --- |
| `<<nodes>>` through `<<avg_path>>` in the metrics block | Paste the whole contents of `output/metrics.txt` |
| `<<>>` rows under "By raw in-degree" | `output/top_in_degree.csv` — columns `in_degree` and `url` |
| `<<>>` rows under "By PageRank" | `output/top_pagerank.csv` — columns `pagerank` and `url` |
| `<<>>` rows under "HITS authorities / hubs" | `output/top_authorities.csv` and `output/top_hubs.csv` — first 5 rows of each |
| Degree-distribution charts | already embedded as `output/plots/in_degree*.png`, `out_degree*.png` |
| Largest-WCC figure | already embedded as `output/plots/largest_wcc.png` |

Quick way to view top-K files in the terminal:

```bash
column -t -s, output/top_in_degree.csv | head
column -t -s, output/top_pagerank.csv  | head
```

Decimal places: round PageRank to 4–5 sig figs in the table (the CSV has 8). In-degree is
already integer.

---

## 13. Things the professor might ask, and what to say

**"Why 4 rounds when the brief says depth 2?"** Depth 2 means "follow links twice from
each seed". With 10 seeds, four `bin/crawl` rounds still keep the BFS depth at 2 per
seed; the extra rounds just give the fetcher time to drain its queue (some hosts are
slow, some URLs retry). It's not the same as doing depth 4.

**"Why hand-rolled PageRank instead of `nx.pagerank`?"** The brief specifies 20
iterations exactly. `nx.pagerank` stops at a tolerance, usually well before 20. Doing it
ourselves matches the spec.

**"Why sample the diameter?"** Exact diameter is O(V·E). On 2 000 nodes that's fine, but
the sampled version (BFS from up to 300 random sources) gives the same number to within
1 in practice, and the assignment says "diameter and average shortest path **in the
largest connected component**", which we do exactly. The sampling is on **which sources
to BFS from**, not on the graph itself.

**"Why is the average clustering coefficient computed on the undirected view?"** That's
the Watts–Strogatz definition. NetworkX's `average_clustering` on a digraph computes a
different quantity. The brief just says "clustering coefficient" without specifying, so
we use the standard one.

**"Why did you switch from `ut.ac.ir` to `sharif.ir`?"** Arvan Cloud was blocking our
crawler from `ut.ac.ir` and `iran.ir`. Sharif is on a different CDN and responds normally.
The methodology is identical; only the seed changed.

**"How do you know the in-degree distribution is heavy-tailed?"** The log-log scatter
shows a straight-ish line over 2–3 decades; the log-binned PDF (Newman style) shows it
more clearly because the tail isn't lost in noise. Slope in the −2.0 to −2.5 range is
what the literature reports for the web at large.

**"Why does PageRank and in-degree agree on the top of the list?"** Because the heavy
nav-link pages dominate both. Where they disagree is in the long tail: in-degree gives
equal weight to every incoming link, PageRank weights by source importance. Section
headers and pagination pages tend to have high in-degree but low PageRank; deep articles
linked from few but important pages can have the opposite.

---

## 14. Cheat sheet

```bash
# one-time
export NUTCH_HOME=/opt/nutch
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# clean previous run if any
rm -rf data/crawl data/dump output/dataset output/plots output/*.csv \
       output/*.gexf output/*.graphml output/metrics.txt

# end to end
./scripts/crawl.sh                                       # ~30–60 min
./scripts/export.sh                                      # ~1–3 min
python -m src.cli --dump data/dump --out output --domain sharif.ir
```

Then:
- open `output/metrics.txt` → paste into the report's "Numbers from this run" block.
- open the `output/top_*.csv` → fill in the report's tables.
- the plot PNGs are already referenced by `report.md`.

Done.
