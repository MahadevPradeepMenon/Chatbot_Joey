# Strategy Document Chunking

## Purpose

The strategy chunking pipeline converts the approved Hey Joey strategy documents into smaller searchable passages for local retrieval.

Embedding or ranking an entire strategy collection as one document would make retrieval too broad. Strategy-level chunking allows Joey to return a specific support strategy or a focused contextual passage while preserving enough surrounding text to remain understandable.

The chunking stage sits between document loading and local retrieval-index construction.

---

## Input

The source corpus contains ten approved Hey Joey strategy documents covering:

- friendship;
- managing social anxiety;
- toilet training;
- sensory processing;
- behavioural challenges and emotional regulation;
- crisis management and safety;
- personal hygiene and self-care;
- eating and mealtime challenges;
- communication skills and language development;
- sleep and bedtime routines.

The local document loader converts the approved source material into cleaned text before chunking.

Processed text is read from:

```text
data/processed/strategies_text/
```

Raw and processed strategy content remains local and is not intended to be committed to the public repository.

---

## Supported Strategy Structure

The source documents contain several strategy-title formats.

Examples include:

```text
Strategy A1: Title
Strategy A2 :: Title
Strategy A1 Title
A1. Title
```

The chunker normalises these variations so that strategy codes and titles can be preserved consistently where available.

---

## Preserved Metadata

Each generated chunk retains source metadata used later for retrieval, evaluation and provenance.

This can include:

- collection title;
- theme;
- strategy code;
- strategy title;
- section type;
- section title;
- original source filename;
- source document hash;
- chunk identifier;
- chunk text.

Keeping this metadata separate from the passage text allows retrieval results to be traced back to their source and supports both lexical weighting and parent-facing evidence display.

---

## Chunk Types

The processed corpus contains two main chunk types.

### Strategy chunks

Strategy chunks contain specific named support strategies and are eligible to be returned as strategy-search results.

### Context chunks

Context chunks contain supporting material such as introductions, implementation guidance and other explanatory content.

Context chunks are retained in the processed corpus and local embedding index, but the evaluated retrieval pipeline is configured to return strategy content as the final ranked result.

---

## Chunking Rules

The final chunking configuration uses:

```text
maximum chunk size = 2,200 characters
paragraph overlap = 1 paragraph
```

The chunker applies the following rules:

- preserve paragraph boundaries where possible;
- avoid splitting strategy content unnecessarily;
- use one paragraph of overlap between neighbouring chunks;
- distinguish strategy and contextual sections;
- retain strategy identity and source provenance;
- keep chunks small enough for focused retrieval while preserving useful context.

The overlap helps reduce information loss when relevant content falls near a chunk boundary.

---

## Final Corpus Snapshot

The final thesis corpus preprocessing produced:

```text
10 source documents
359 total chunks
257 strategy chunks
102 context chunks
34 unique strategy codes
approximately 64,886 words
```

Only the 257 strategy chunks were eligible as final strategy retrieval results in the thesis evaluation.

The 102 context chunks remained available in the processed corpus and local semantic index for supporting context and provenance.

---

## Outputs

The chunking pipeline produces local structured outputs including:

```text
strategy_chunks.jsonl
strategy_chunks.csv
strategy_chunk_manifest.json
```

These files support:

- inspection of generated chunks;
- reproducible embedding-index creation;
- lexical and semantic retrieval;
- retrieval evaluation;
- source provenance;
- corpus statistics.

Generated strategy-content artifacts are runtime/research assets and are excluded from the public Git repository.

---

## Relationship to Retrieval

The generated chunks are used by several later retrieval stages.

### BM25 retrieval

`rag/bm25_retriever.py`

BM25 uses passage text together with weighted metadata such as collection, theme, strategy title and section title.

### Semantic retrieval

`rag/semantic_retriever.py`

Semantic retrieval compares the query embedding with locally generated chunk embeddings.

### Hybrid retrieval

`rag/hybrid_retriever.py`

Hybrid retrieval combines BM25 and semantic ranked lists using Reciprocal Rank Fusion.

The chunking stage is therefore shared by all final retrieval methods except the original rule-based baseline.

---

## Local Embedding Index

After chunking, the local embedding index is created with:

```powershell
python -m rag.build_embedding_index
```

The final semantic model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model produces normalised 384-dimensional `float32` embeddings.

No paid external model API or hosted vector database is required for normal retrieval.

---

## Privacy and Repository Boundary

Raw strategy documents, cleaned strategy text, generated chunks and embedding indexes remain local.

They are excluded from Git and from the Docker build context because they may contain proprietary or non-public Hey Joey strategy content.

The public repository contains the processing and retrieval code, but not the private strategy corpus itself.

This separation supports reproducibility of the software architecture without publishing the underlying approved content.

---

## Current Limitations

Chunking decisions affect retrieval quality.

Possible limitations include:

- a relevant idea being split across neighbouring chunks;
- overlap introducing repeated information;
- inconsistent source formatting affecting strategy-title detection;
- contextual material being separated from the most relevant strategy;
- metadata extraction depending on document structure;
- one fixed maximum chunk size not being optimal for every collection.

The final thesis evaluation measured retrieval behaviour after this chunking process, but it did not independently compare alternative chunk sizes or overlap strategies.

Future work could evaluate:

- different chunk-size limits;
- different overlap amounts;
- strategy-boundary-aware chunking;
- section-aware semantic segmentation;
- corpus-specific chunking rules;
- expert review of chunk quality.

---

## Relationship to the MSc Thesis

The chunking pipeline supports the retrieval experiment reported in the dissertation.

The same processed corpus was used for:

- BM25-only retrieval;
- Semantic-only retrieval;
- Hybrid Reciprocal Rank Fusion retrieval.

The final retrieval evaluation used 30 synthetic queries across the ten strategy collections with `top_k = 3`.

Chunking itself was not evaluated as a separate experiment, so the thesis results should not be interpreted as proving that the chosen chunk size or overlap is optimal.

The corpus and chunking configuration should instead be understood as fixed preprocessing conditions under which the retrieval methods were compared.

---

## Main Implementation Files

```text
rag/document_loader.py
rag/strategy_chunker.py
rag/build_embedding_index.py
rag/bm25_retriever.py
rag/semantic_retriever.py
rag/hybrid_retriever.py
```

---

## Current Pipeline Position

```text
approved local strategy documents
→ document loading and cleaning
→ strategy/context section detection
→ chunking with provenance
→ local chunk artifacts
→ embedding-index construction
→ BM25 / semantic retrieval
→ Hybrid RRF
→ confidence assessment
→ source-backed strategy response
```

The chunking stage is therefore a completed part of the final local retrieval pipeline rather than a preliminary step awaiting semantic retrieval.
