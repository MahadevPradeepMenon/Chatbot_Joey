# Semantic Strategy Retrieval

## Purpose

The semantic strategy retriever searches the locally generated Hey Joey strategy index using a parent or carer's natural-language strategy question.

Unlike exact keyword matching, semantic retrieval compares the meaning of the submitted query with the meaning of indexed strategy passages. This helps when parent or carer wording differs from the terminology used in the approved Hey Joey strategy documents.

Semantic retrieval is one component of the final retrieval architecture. The application also uses BM25 lexical retrieval and combines the two ranked lists using Reciprocal Rank Fusion.

---

## Inputs

The semantic retriever loads the local index artifacts:

```text
strategy_embeddings.npy
strategy_index_metadata.jsonl
strategy_index_manifest.json
```

These files are generated locally from the processed Hey Joey strategy corpus.

The final corpus snapshot contains:

```text
10 approved strategy documents
359 total chunks
257 strategy chunks
102 context chunks
34 unique strategy codes
approximately 64,886 words
```

The index contains both strategy and contextual chunks, while final strategy-search results are restricted to eligible strategy content.

---

## Embedding Model

The retriever uses the same local model used to create the embedding index:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model produces:

```text
384-dimensional embeddings
float32 values
unit-normalised vectors
```

Using the same model for indexing and query encoding ensures that stored chunks and incoming questions are represented in the same vector space.

No paid external model API is required.

---

## Retrieval Process

At query time, the semantic retriever:

1. validates and loads the local embedding index and metadata;
2. loads the same sentence-transformer model used during indexing;
3. converts the parent or carer question into a local embedding;
4. normalises the query vector;
5. compares the query vector with stored chunk embeddings;
6. ranks candidate chunks by semantic similarity;
7. filters or deduplicates results so repeated chunks from the same strategy do not dominate;
8. returns eligible strategy evidence together with source provenance.

Because both stored and query vectors are unit-normalised, cosine similarity can be computed efficiently using a dot product.

---

## Returned Evidence

A semantic retrieval result can include:

- rank;
- semantic similarity score;
- strategy code;
- strategy title;
- collection title;
- theme;
- source filename;
- chunk identifier;
- supporting passage.

This metadata allows later workflow components to display source-backed strategy evidence rather than only an opaque similarity score.

---

## Default Role in the Final System

The semantic retriever remains available as a standalone retrieval method for evaluation and debugging.

In the current application, however, strategy search normally uses the Hybrid RRF pipeline rather than Semantic-only retrieval by itself.

The application flow is:

```text
parent/carer strategy question
→ safety screening
→ privacy-reduced context construction
→ BM25 retrieval
   +
   semantic retrieval
→ Reciprocal Rank Fusion
→ confidence assessment
→ abstain or continue
→ bounded history-aware ranking
→ source-backed strategy response
```

Semantic retrieval therefore supplies one ranked list to the final hybrid system.

---

## Candidate and Top-K Behaviour

For the final thesis retrieval comparison, the common evaluation settings were:

```text
candidate pool = 30
top_k = 3
```

The semantic retriever can return more candidates internally, but final evaluation used the top three results for ranking metrics.

The current application can request a configurable number of final strategy results within the workflow's allowed limits.

---

## Similarity Scores

Semantic similarity scores are comparative ranking signals.

They are not:

- probabilities;
- clinical confidence values;
- calibrated estimates of correctness;
- measures of therapeutic effectiveness.

A higher score only indicates that the query embedding is more similar to a stored passage embedding under the selected model.

The separate retrieval-confidence layer decides whether the available evidence is strong enough to return ordinary strategy support.

---

## Confidence and Abstention

`rag/retrieval_confidence.py`

A semantically top-ranked result is not automatically treated as reliable evidence.

After retrieval, the confidence layer considers signals including:

- meaningful query-to-evidence token overlap;
- retrieval score;
- the amount of useful query evidence;
- whether the evidence is sufficient to support an answer.

Weak evidence leads to abstention rather than presenting a poorly supported strategy.

This distinction is important because semantic similarity alone does not guarantee human-perceived relevance.

---

## Hybrid Reciprocal Rank Fusion

`rag/hybrid_retriever.py`

The final application combines Semantic-only and BM25-only ranked lists using Reciprocal Rank Fusion.

The final thesis configuration used:

```text
RRF k = 60
candidate pool = 30
top_k = 3
```

RRF operates on rank positions rather than directly mixing BM25 and cosine-similarity scores, which exist on different numerical scales.

This allows lexical and semantic evidence to contribute without assuming the raw scores are directly comparable.

---

## Baseline Preservation

The project retains multiple retrieval methods so they can be compared under the same evaluation conditions.

The relevant implementations include:

```text
rag/strategy_retriever.py      # original rule-based baseline
rag/bm25_retriever.py          # lexical baseline
rag/semantic_retriever.py      # semantic retrieval
rag/hybrid_retriever.py        # BM25 + semantic RRF
```

The original rule-based retriever is therefore preserved as an evaluation baseline, not as the current application default.

---

## Relationship to the MSc Thesis

The final thesis retrieval experiment compared four methods on the same 30 synthetic queries across the ten strategy collections:

| Retriever | Hit@1 | Hit@3 | MRR | Mean warm-run latency |
|---|---:|---:|---:|---:|
| Rule-based baseline | 40.0% | 50.0% | 0.4500 | 0.615 ms |
| BM25-only | 66.7% | 86.7% | 0.7611 | 4.316 ms |
| Semantic-only | 86.7% | 90.0% | 0.8833 | 28.765 ms |
| Hybrid RRF | 86.7% | 90.0% | 0.8833 | 30.142 ms |

Semantic-only retrieval produced the strongest improvement over the simpler baselines.

Hybrid RRF achieved the same Hit@1, Hit@3 and MRR values as Semantic-only retrieval on the final dataset. It therefore matched rather than exceeded Semantic-only ranking performance.

The result supports the conclusion that semantic representations handled wording variation more effectively than the simpler lexical and rule-based baselines on this fixed synthetic dataset.

These results do not establish universal retrieval quality or clinical effectiveness.

---

## Error Patterns

The final retrieval error analysis identified failures involving informal or paraphrased queries.

Examples included cases related to:

- toilet training;
- communication;
- social anxiety.

These failures may reflect several factors:

- limitations of the embedding model;
- corpus wording;
- chunking decisions;
- query construction;
- collection-level relevance labels;
- ambiguity between multiple potentially useful support collections.

Future work should therefore evaluate semantic retrieval using larger independently reviewed datasets and, where possible, domain-expert relevance judgements.

---

## Privacy

Parent or carer queries and Hey Joey strategy content are embedded locally.

The following remain local runtime/research assets:

- raw strategy documents;
- cleaned text;
- processed chunks;
- embedding arrays;
- index metadata;
- index manifests.

No OpenAI, Claude or other paid external language-model API is required for normal semantic retrieval.

The public repository contains the retrieval code but not the private strategy corpus or generated indexes.

---

## Current Limitations

Semantic retrieval has several important limitations:

- semantic similarity does not guarantee human-perceived relevance;
- the selected embedding model may not be optimal for Hey Joey terminology;
- chunking affects what meaning is represented in each vector;
- query wording can still influence ranking substantially;
- local semantic retrieval is slower than Rule-based or BM25-only retrieval;
- the final evaluation uses only 30 synthetic queries;
- retrieval relevance was assessed at collection level rather than through independent multi-rater expert judgement;
- the system has not been validated for clinical effectiveness.

Future work could compare:

- alternative sentence-embedding models;
- different chunking strategies;
- domain-adapted embeddings;
- larger candidate pools;
- expert-created relevance labels;
- multilingual retrieval if required.

---

## Main Implementation Files

```text
rag/build_embedding_index.py
rag/semantic_retriever.py
rag/hybrid_retriever.py
rag/retrieval_confidence.py
app/context_builder.py
app/strategy_workflow_service.py
```

Relevant evaluation code includes:

```text
evaluation/run_retrieval_comparison.py
evaluation/test_retrieval_confidence.py
```

---

## Current Status

Semantic retrieval is fully implemented and integrated into the final Hey Joey retrieval pipeline.

It is no longer a future stage awaiting conversational integration.

The current architecture uses semantic retrieval alongside BM25 as part of Hybrid RRF, followed by confidence-based abstention and source-backed response construction.
