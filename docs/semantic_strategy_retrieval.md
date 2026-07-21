# Semantic Strategy Retrieval

## Purpose

The semantic strategy retriever searches the locally generated Hey Joey
strategy index using a parent's natural-language description.

Unlike exact keyword matching, semantic retrieval compares the meaning
of a parent query with the meaning of each indexed strategy passage.

## Inputs

The retriever loads:

- `strategy_embeddings.npy`
- `strategy_index_metadata.jsonl`
- `strategy_index_manifest.json`

These files were generated locally from 359 chunks across 10 approved
strategy collections.

## Retrieval Process

1. Validate the embedding index and metadata.
2. Load the same local embedding model used during indexing.
3. Convert the parent query into a normalised embedding.
4. Compare it with all strategy embeddings using a dot product.
5. Rank passages by cosine similarity.
6. Return strategy titles, passages and source documents.

## Default Behaviour

By default, the retriever:

- returns five results;
- returns strategy sections rather than general context sections;
- prevents multiple chunks from the same strategy dominating the results;
- includes source provenance;
- runs locally without a paid API.

## Similarity Scores

Similarity scores are comparative ranking signals.

They are not probabilities, clinical confidence values or measures of
system accuracy. A higher score only indicates that a strategy passage
is more semantically similar to the submitted query.

## Privacy

Parent queries and Hey Joey strategy content are embedded locally.

No OpenAI, Claude or other paid language-model API is used.

## Baseline Preservation

The existing rule-based retriever remains in the project as a baseline.
The semantic retriever is implemented separately so both retrieval
methods can be compared during evaluation.

## Next Stage

The next stage will integrate source-backed semantic retrieval into the
Joey conversational workflow and safety-aware response builder.