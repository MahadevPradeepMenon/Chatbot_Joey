# Local Semantic Embedding Index

## Purpose

The local semantic embedding index converts processed Hey Joey strategy chunks into numerical vector representations that can be searched by semantic similarity.

This allows the retrieval pipeline to match parent or carer wording with strategy passages even when the query and source document do not use the same vocabulary.

The embedding index is one component of the final local retrieval architecture. It supports Semantic-only retrieval directly and also contributes to the Hybrid Reciprocal Rank Fusion pipeline alongside BM25 lexical retrieval.

---

## Input

The index builder reads the processed chunk file:

```text
data/processed/strategy_chunks/strategy_chunks.jsonl
```

The final corpus snapshot contains:

```text
10 approved strategy documents
359 total chunks
257 strategy chunks
102 context chunks
34 unique strategy codes
approximately 64,886 words
```

Both strategy and context chunks are retained in the processed corpus and embedding index. The evaluated retrieval pipeline is configured so that final strategy-search results come from strategy content.

---

## Embedding Model

The pipeline uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model runs locally and produces:

```text
384-dimensional embeddings
float32 values
unit-normalised vectors
```

The vectors are normalised so semantic similarity can be computed efficiently using a dot product equivalent to cosine similarity for unit-length vectors.

No paid external model API is required.

---

## Local Model Availability

For a local Python setup, the sentence-transformer model is downloaded during initial setup if it is not already present in the local cache.

After the model files are available, embedding generation and semantic retrieval can operate locally.

The Docker image preloads the model during the image build so a normal container start does not need to download the semantic model on the first strategy request.

Initial package installation or Docker image construction may still require internet access to obtain dependencies and model files.

---

## Index Outputs

The index builder creates:

```text
strategy_embeddings.npy
strategy_index_metadata.jsonl
strategy_index_manifest.json
```

### `strategy_embeddings.npy`

Stores the numerical embedding matrix.

Each row represents one processed chunk embedding.

### `strategy_index_metadata.jsonl`

Stores the metadata associated with each embedding row.

Metadata can include:

- chunk identifier;
- embedding position;
- collection title;
- theme;
- strategy code;
- strategy title;
- section information;
- source filename;
- source document hash;
- passage text or search metadata needed by retrieval.

The `embedding_position` field links one metadata record to the corresponding row in the embedding array.

### `strategy_index_manifest.json`

Stores index-level information used to inspect or validate the generated artifact, such as corpus and model metadata.

---

## Row Alignment

The embedding matrix and metadata file rely on positional alignment.

Conceptually:

```text
embedding row 0  ↔ metadata record with embedding_position 0
embedding row 1  ↔ metadata record with embedding_position 1
embedding row 2  ↔ metadata record with embedding_position 2
...
```

This relationship is validated during index construction so retrieval can safely map a similarity score back to the correct source chunk.

---

## Validation

The build pipeline validates the generated index before it is used.

Checks include:

- unique chunk identifiers;
- non-empty search text;
- matching metadata and embedding counts;
- a valid two-dimensional embedding matrix;
- the expected embedding dimensionality;
- finite numerical values;
- absence of `NaN` values;
- absence of infinite values;
- unit-normalised vectors;
- valid row-to-metadata alignment.

These checks help identify preprocessing or model-output errors before the index reaches the retrieval layer.

---

## Building the Index

The local index can be generated from the project root with:

```powershell
python -m rag.build_embedding_index
```

The expected sequence is:

```text
approved local strategy documents
→ cleaned strategy text
→ strategy/context chunks
→ local sentence embeddings
→ embedding array + metadata + manifest
```

The generated index is a runtime/research artifact rather than source code.

---

## Semantic Retrieval

`rag/semantic_retriever.py`

At query time, the semantic retriever:

1. loads the generated embedding matrix and metadata;
2. embeds the parent or carer query using the same local sentence-transformer model;
3. normalises the query vector;
4. compares the query vector with stored chunk vectors;
5. ranks chunks by semantic similarity;
6. returns the highest-ranked eligible strategy evidence with source metadata.

Because stored and query vectors are normalised, the implementation can calculate cosine similarity using a vector dot product.

---

## Hybrid Retrieval

`rag/hybrid_retriever.py`

The final application combines Semantic retrieval with BM25 lexical retrieval using Reciprocal Rank Fusion.

The final thesis configuration used:

```text
RRF k = 60
candidate pool = 30
top_k = 3
```

The hybrid layer combines rank positions rather than directly combining BM25 and semantic scores, since the two scoring systems use different numerical scales.

The embedding index therefore supports one half of the final hybrid retrieval architecture.

---

## Relationship to the MSc Thesis

The same local embedding model and index supported both:

- Semantic-only retrieval;
- Hybrid RRF retrieval.

The final retrieval experiment used 30 synthetic queries across the ten strategy collections.

Reported results were:

| Retriever | Hit@1 | Hit@3 | MRR | Mean warm-run latency |
|---|---:|---:|---:|---:|
| Semantic-only | 86.7% | 90.0% | 0.8833 | 28.765 ms |
| Hybrid RRF | 86.7% | 90.0% | 0.8833 | 30.142 ms |

Semantic-only and Hybrid RRF achieved the same ranking metrics on the final dataset.

These results evaluate the complete retrieval methods under one fixed preprocessing and embedding configuration. They do not independently demonstrate that `all-MiniLM-L6-v2` is the optimal embedding model for Hey Joey.

---

## Privacy and Repository Boundary

The following artifacts remain local:

- raw strategy documents;
- cleaned strategy text;
- processed chunks;
- embedding arrays;
- index metadata;
- index manifests.

They are excluded from Git and from the Docker build context because they may contain proprietary or non-public Hey Joey strategy content.

The public repository contains the code needed to build and query the index, but not the private strategy corpus itself.

This allows the retrieval architecture to remain inspectable without publishing the underlying strategy content.

---

## Current Limitations

The semantic index has several limitations:

- embedding quality depends on the selected sentence-transformer model;
- semantic similarity does not guarantee human-perceived relevance;
- chunking choices influence what information is represented in each vector;
- the index must be rebuilt when the source corpus changes;
- query latency is higher than Rule-based or BM25-only retrieval;
- the current evaluation uses a small synthetic dataset;
- no independent expert comparison of alternative embedding models has been completed.

Future work could compare:

- alternative sentence-embedding models;
- different chunking strategies;
- dimensionality or model-size trade-offs;
- approximate nearest-neighbour indexing for larger corpora;
- expert-created relevance judgements;
- multilingual or domain-adapted embeddings if required.

---

## Main Implementation Files

```text
rag/document_loader.py
rag/strategy_chunker.py
rag/build_embedding_index.py
rag/semantic_retriever.py
rag/hybrid_retriever.py
```

Relevant evaluation code includes:

```text
evaluation/run_retrieval_comparison.py
```

---

## Current Pipeline Position

```text
approved strategy corpus
→ document loading
→ chunking
→ all-MiniLM-L6-v2 embeddings
→ local embedding index
→ Semantic retrieval
          +
       BM25 retrieval
→ Reciprocal Rank Fusion
→ confidence assessment
→ source-backed strategy response
```

The local embedding index is therefore a completed and actively used part of the final Hey Joey retrieval pipeline rather than a preparatory stage awaiting semantic retrieval.
