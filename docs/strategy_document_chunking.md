# Strategy Document Chunking

## Purpose

The strategy chunking pipeline divides the revised Hey Joey strategy collections into smaller searchable passages.

Embedding entire collections as single documents would make retrieval too broad. Strategy-level chunks allow Joey to retrieve a specific support strategy rather than an entire collection.

## Input

The chunker reads cleaned text from:

`data/processed/strategies_text/`

These files were created by the local document loader from eight DOCX files and one plain-text file.

## Supported Structure

The revised source documents use several strategy-title formats:

- `Strategy A1: Title`
- `Strategy A2 :: Title`
- `Strategy A1 Title`
- `A1. Title`

The chunker preserves:

- collection title
- theme
- strategy code
- strategy title
- original source filename
- source document hash
- chunk text

## Chunking Rules

- Maximum chunk size: 2,200 characters
- Paragraph boundaries are preserved where possible
- One paragraph overlaps between neighbouring chunks
- Strategy and contextual sections are identified separately
- Source provenance is retained for every chunk

## Outputs

The pipeline produces:

- `strategy_chunks.jsonl`
- `strategy_chunks.csv`
- `strategy_chunk_manifest.json`

## Privacy

Generated chunks remain local and are excluded from Git because they contain Hey Joey strategy content.

## Next Stage

The next stage creates local semantic embeddings for each chunk and stores them in a local searchable index without using a paid API.