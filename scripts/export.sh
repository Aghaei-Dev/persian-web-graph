#!/usr/bin/env bash
# Dump the link structure and per-page metadata from the Nutch crawl.
#
# Produces three text artefacts the Python pipeline consumes:
#   data/dump/crawldb.txt       — one record per known URL (status, score, anchor, title)
#   data/dump/linkdb.txt        — for each URL, the list of inbound URLs
#   data/dump/webgraph/         — Nutch WebGraph (nodes/, outlinks/, inlinks/)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

: "${NUTCH_HOME:?Set NUTCH_HOME to your apache-nutch-1.20 directory}"

CRAWL_DIR="$ROOT/data/crawl"
DUMP_DIR="$ROOT/data/dump"

mkdir -p "$DUMP_DIR"
rm -rf "$DUMP_DIR/crawldb_raw" "$DUMP_DIR/linkdb_raw" "$DUMP_DIR/webgraph"

# 1) Readable CrawlDb dump (status, score, signature, metadata, fetched title where present).
"$NUTCH_HOME/bin/nutch" readdb "$CRAWL_DIR/crawldb" -dump "$DUMP_DIR/crawldb_raw"
mv "$DUMP_DIR/crawldb_raw/part-r-00000" "$DUMP_DIR/crawldb.txt"
rm -rf "$DUMP_DIR/crawldb_raw"

# 2) LinkDb dump — inbound link graph.
"$NUTCH_HOME/bin/nutch" readlinkdb "$CRAWL_DIR/linkdb" -dump "$DUMP_DIR/linkdb_raw"
mv "$DUMP_DIR/linkdb_raw/part-r-00000" "$DUMP_DIR/linkdb.txt"
rm -rf "$DUMP_DIR/linkdb_raw"

# 3) Built-in WebGraph job: nodes + outlinks + inlinks as SequenceFiles, then text dump.
SEG_DIR="$CRAWL_DIR/segments"
WG_DIR="$DUMP_DIR/webgraph"
"$NUTCH_HOME/bin/nutch" webgraph -segmentDir "$SEG_DIR" -webgraphdb "$WG_DIR"

# Text dumps of the WebGraph for easier parsing in Python.
"$NUTCH_HOME/bin/nutch" nodedumper -outlinks -webgraphdb "$WG_DIR" -output "$WG_DIR/outlinks_txt"
"$NUTCH_HOME/bin/nutch" nodedumper -inlinks  -webgraphdb "$WG_DIR" -output "$WG_DIR/inlinks_txt"
"$NUTCH_HOME/bin/nutch" nodedumper -scores   -webgraphdb "$WG_DIR" -output "$WG_DIR/scores_txt"

# 4) Per-page title + outlink list, mined from each fetched segment.
SEG_TXT="$DUMP_DIR/segments_text"
rm -rf "$SEG_TXT"
mkdir -p "$SEG_TXT"
for seg in "$SEG_DIR"/*/; do
  name="$(basename "$seg")"
  # Keep parse_data (has title + outlinks); skip raw content and parse_text to keep the dump small.
  "$NUTCH_HOME/bin/nutch" readseg \
    -dump "$seg" "$SEG_TXT/$name" \
    -nocontent -noparsetext
done

echo "Dumps ready under: $DUMP_DIR"
