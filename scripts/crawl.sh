#!/usr/bin/env bash
# Run a depth-2 Nutch crawl capped at ~2000 fetched pages.
#
# Required env:
#   NUTCH_HOME  — path to apache-nutch-1.20 install (the one that contains bin/nutch)
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

: "${NUTCH_HOME:?Set NUTCH_HOME to your apache-nutch-1.20 directory}"

CONF_SRC="$ROOT/nutch/conf"
SEED_DIR="$ROOT/nutch/urls"
CRAWL_DIR="$ROOT/data/crawl"

# Copy our overrides into the Nutch conf dir (Nutch reads them from there).
cp "$CONF_SRC/nutch-site.xml"     "$NUTCH_HOME/conf/nutch-site.xml"
cp "$CONF_SRC/regex-urlfilter.txt" "$NUTCH_HOME/conf/regex-urlfilter.txt"

mkdir -p "$CRAWL_DIR"

# bin/crawl <seedDir> <crawlDir> <numRounds>
# topN per round is tuned so two rounds fetch at most ~2000 docs total.
"$NUTCH_HOME/bin/crawl" \
  -i \
  -s "$SEED_DIR" \
  --num-fetchers 1 \
  --num-threads 10 \
  --size-fetchlist 1000 \
  "$CRAWL_DIR" \
  2

echo "Crawl finished. CrawlDb / LinkDb / segments are in: $CRAWL_DIR"
