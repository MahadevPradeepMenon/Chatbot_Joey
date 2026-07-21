# Local Semantic Embedding Index

## Purpose

The local semantic embedding index converts the processed Hey Joey
strategy chunks into numerical vector representations.

This allows later retrieval to compare a parent note with strategy
passages according to semantic meaning rather than relying only on
exact keyword matches.

## Input

The index builder reads:

`data/processed/strategy_chunks/strategy_chunks.jsonl`

The current corpus contains 10 approved strategy documents divided into
359 searchable chunks.

## Embedding Model

The pipeline uses:

`sentence-transformers/all-MiniLM-L6-v2`

The model runs locally on the CPU. The model files are downloaded during
the initial setup, after which embedding generation can run locally.

## Index Structure

The pipeline creates:

- `strategy_embeddings.npy`
- `strategy_index_metadata.jsonl`
- `strategy_index_manifest.json`

The embedding array and metadata file use matching row positions. Each
metadata record contains an `embedding_position` field corresponding to
one row in the numerical embedding array.

## Validation

The pipeline validates:

- unique chunk identifiers
- non-empty search text
- matching chunk and embedding counts
- valid two-dimensional embedding shape
- absence of NaN and infinite values
- unit-normalised vectors

## Privacy

The source strategies, processed text, chunks and generated index remain
local and are excluded from Git.

No paid language-model API is required for embedding generation.

## Next Stage

The next stage will load this index, embed a parent query locally and
retrieve the most semantically relevant Hey Joey strategy chunks.