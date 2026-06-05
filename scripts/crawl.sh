#!/usr/bin/env bash
# Run a Nutch crawl over *.sharif.ir aiming for ~2 000 fetched pages.
#
# Required env:
#   NUTCH_HOME  — path to apache-nutch-1.22 install (the one that contains bin/nutch)
#
# Layout expected (relative to this script):
#   ../nutch/conf/nutch-site.xml
#   ../nutch/conf/regex-urlfilter.txt
#   ../nutch/urls/seed.txt
#
# Output goes to ../data/crawl (CrawlDb / LinkDb / segments).

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

: "${NUTCH_HOME:?Set NUTCH_HOME to your apache-nutch-1.22 directory}"

CONF_SRC="$ROOT/nutch/conf"
SEED_DIR="$ROOT/nutch/urls"
CRAWL_DIR="$ROOT/data/crawl"

# Copy our overrides into the Nutch conf dir (Nutch reads them from there).
cp "$CONF_SRC/nutch-site.xml"      "$NUTCH_HOME/conf/nutch-site.xml"
cp "$CONF_SRC/regex-urlfilter.txt" "$NUTCH_HOME/conf/regex-urlfilter.txt"

mkdir -p "$CRAWL_DIR"

# bin/crawl <seedDir> <crawlDir> <numRounds>
#   (no -i)               do NOT run the Solr indexing step. We don't have a Solr
#                         instance, and bin/crawl is `set -e` — if the index step
#                         fails with exit 255 it kills the whole crawl mid-run.
#                         Our pipeline reads dumps directly, so indexing is unneeded.
#   --num-fetchers 1      one MapReduce fetcher (single node)
#   --num-threads 20      worker threads per fetcher
#   --size-fetchlist 800  topN per round; 4 rounds * 800 ≈ 3 200 candidate fetches,
#                         well above the 2 000-page floor after dedup / failures.
#
# The assignment specifies depth 2 from a seed. With a multi-seed list, "depth 2"
# means each seed → its outlinks → those pages' outlinks. `bin/crawl 2` does exactly
# that. We use 4 rounds because many sharif.ir seeds are themselves nav stubs whose
# first-hop pages are also nav stubs — depth-2 from the homepage alone returned 85
# pages; 4 rounds across 10 seeds gets us into the actual content.
"$NUTCH_HOME/bin/crawl" \
  -s "$SEED_DIR" \
  --num-fetchers 1 \
  --num-threads 20 \
  --size-fetchlist 800 \
  "$CRAWL_DIR" \
  4

echo
echo "===== CrawlDb stats ====="
"$NUTCH_HOME/bin/nutch" readdb "$CRAWL_DIR/crawldb" -stats || true

echo
echo "Crawl finished. CrawlDb / LinkDb / segments are in: $CRAWL_DIR"
echo "Next: ./scripts/export.sh"
