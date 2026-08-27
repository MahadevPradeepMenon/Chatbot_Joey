# Joey Strategy Retrieval Layer

## Purpose

The strategy retrieval layer connects parent or carer questions and structured Hey Joey context to relevant support content from an approved local strategy corpus.

The current implementation is a local, source-backed retrieval pipeline rather than the earlier rule-based prototype. It combines lexical and semantic retrieval, confidence-based abstention and limited history-aware ranking.

The wider workflow does not depend on a generative language model. Retrieved evidence is used to assemble cautious support responses, while safety screening, confidence checks and persistence remain explicit and testable.

---

## Current Workflow

1. A parent or carer asks a strategy question in the Streamlit interface.
2. The FastAPI strategy workflow screens the question for safety concerns.
3. If a safety concern takes priority, ordinary strategy retrieval is not performed.
4. A privacy-reduced contextual query is built from relevant available context.
5. BM25 lexical retrieval and local semantic retrieval search the approved strategy corpus.
6. Reciprocal Rank Fusion combines the two ranked lists.
7. Retrieval confidence is assessed.
8. Joey abstains when the available evidence is too weak.
9. Relevant strategy evidence can receive small history-aware ranking adjustments based on stored usage or feedback.
10. Joey returns source-backed strategy options with cautious wording and evidence provenance.
11. Optional parent or carer feedback can be stored for later ranking decisions.

The record-observation workflow remains separate and still requires explicit confirmation before a structured journal record is saved.

---

## Current Strategy Corpus

The final prototype uses ten approved Hey Joey strategy documents covering:

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

The processed corpus contains:

- 359 total chunks;
- 257 strategy chunks;
- 102 contextual chunks;
- 34 unique strategy codes.

Strategy chunks are eligible retrieval results. Contextual chunks are retained in the processed corpus and local embedding index for supporting context and provenance.

Raw strategy documents, processed text and generated embedding indexes are local runtime assets and are intentionally excluded from the public repository.

Approved source documents are expected under:

```text
data/raw/strategies/
```

The local embedding index can be generated with:

```powershell
python -m rag.build_embedding_index
```

---

## Retrieval Components

### Rule-Based Baseline

`rag/strategy_retriever.py`

The original deterministic retrieval method is retained as an evaluation baseline. It represents the simplest retrieval approach used in the thesis comparison, but it is not the current production retrieval method.

### BM25 Lexical Retrieval

`rag/bm25_retriever.py`

BM25 provides lexical retrieval using token overlap and weighted strategy metadata. The implementation uses:

```text
k1 = 1.5
b = 0.75
```

Metadata such as collection, theme, strategy title and section title contributes additional lexical evidence.

### Semantic Retrieval

`rag/semantic_retriever.py`

Semantic retrieval uses the local model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model produces normalised 384-dimensional `float32` embeddings. Query and strategy embeddings are compared locally using cosine similarity implemented through dot products between normalised vectors.

No external model API or hosted vector database is required.

### Hybrid Reciprocal Rank Fusion

`rag/hybrid_retriever.py`

The current retrieval pipeline combines BM25 and semantic ranked lists using Reciprocal Rank Fusion (RRF).

The final evaluation used:

```text
RRF k = 60
candidate pool = 30
top_k = 3
```

RRF combines rank positions rather than directly mixing BM25 and semantic scores, which operate on different numerical scales.

---

## Context Construction

`app/context_builder.py`

Strategy search can include a privacy-reduced subset of available Hey Joey context.

The context builder selects only information relevant to the current question and omits fields that are unnecessary for retrieval. This supports contextual retrieval without sending a complete user profile or conversation state into the retrieval query.

The final retrieval query can include:

- the current parent or carer question;
- relevant profile information;
- relevant recent journal context;
- relevant Quick Track information;
- relevant active-strategy information.

Sensitive or irrelevant fields are deliberately omitted.

---

## Confidence and Abstention

`rag/retrieval_confidence.py`

Retrieval systems always rank something first, even when the available evidence is weak. Joey therefore evaluates retrieval confidence before presenting ordinary strategy suggestions.

The confidence logic considers evidence signals including:

- meaningful query-to-evidence token overlap;
- retrieval score;
- the amount of useful query evidence;
- whether the available result is strong enough to support an answer.

The system can classify retrieval evidence as strong, moderate or weak. Weak evidence leads to abstention rather than presenting a poorly supported strategy.

The thesis tested minimum meaningful-token overlap requirements of at least 1, 2 and 3. On the final 30-query confidence dataset, an overlap threshold of at least 2 produced the highest tested overall decision accuracy of 83.3%, with 46.7% coverage.

These confidence values are operational heuristics rather than calibrated probabilities.

---

## History-Aware Ranking

`rag/strategy_history_ranker.py`

`rag/history_aware_strategy_service.py`

Stored strategy usage and parent or carer feedback can make small, bounded adjustments to otherwise relevant retrieval results.

Examples include:

- a modest positive adjustment for an active strategy;
- positive feedback breaking a close tie;
- negative feedback reducing a strategy's personalised score;
- unseen strategies being identified as new options.

History does not replace retrieval relevance. The adjustment is intentionally limited so that previous feedback cannot overwhelm the underlying source evidence.

---

## Evidence and Provenance

Returned strategy results preserve source metadata so the application can show where a suggestion came from.

Evidence can include:

- strategy code;
- strategy title;
- collection title;
- source filename;
- theme;
- chunk identifier;
- supporting passage;
- original retrieval score;
- history adjustment;
- personalised score;
- history note.

This makes retrieval behaviour more inspectable than a free-form generated answer.

---

## Safety Boundary

Safety screening takes priority over ordinary strategy retrieval.

Joey should:

- avoid diagnosis and treatment claims;
- avoid medication or dosage recommendations;
- avoid advising medication changes;
- avoid claiming certainty about causes;
- detect direct safety or self-injury concerns;
- stop ordinary strategy retrieval when a safety concern takes priority;
- use retrieved strategies as support rather than clinical advice;
- preserve source evidence and cautious wording;
- abstain when retrieval evidence is insufficient.

Safety screening is deterministic and cannot guarantee recognition of every indirect, ambiguous or unusual expression of risk.

---

## Relationship to the MSc Thesis

The final thesis retrieval experiment compared four methods on the same 30 synthetic strategy queries:

| Retriever | Hit@1 | Hit@3 | MRR | Mean warm-run latency |
|---|---:|---:|---:|---:|
| Rule-based baseline | 40.0% | 50.0% | 0.4500 | 0.615 ms |
| BM25-only | 66.7% | 86.7% | 0.7611 | 4.316 ms |
| Semantic-only | 86.7% | 90.0% | 0.8833 | 28.765 ms |
| Hybrid RRF | 86.7% | 90.0% | 0.8833 | 30.142 ms |

Semantic-only retrieval produced the strongest improvement over the simpler baselines. Hybrid RRF matched Semantic-only retrieval on the final dataset but did not improve the ranking metrics further.

The application nevertheless retains Hybrid RRF as the default retrieval architecture because it combines direct lexical evidence with semantic similarity in a transparent rank-fusion process.

These results apply only to the fixed synthetic evaluation dataset. They do not establish universal retrieval quality, clinical effectiveness or production readiness.

---

## Main Implementation Files

```text
app/context_builder.py
app/strategy_workflow_service.py

rag/document_loader.py
rag/strategy_chunker.py
rag/build_embedding_index.py
rag/strategy_retriever.py
rag/bm25_retriever.py
rag/semantic_retriever.py
rag/hybrid_retriever.py
rag/retrieval_confidence.py
rag/strategy_history_ranker.py
rag/history_aware_strategy_service.py

evaluation/run_retrieval_comparison.py
evaluation/test_retrieval_confidence.py
evaluation/test_history_aware_strategy.py
evaluation/test_stored_feedback_ranking.py
```

---

## Current Status

The original rule-based retrieval layer has been superseded by the local hybrid retrieval pipeline.

The current architecture is:

```text
parent/carer strategy question
→ deterministic safety screening
→ privacy-reduced context construction
→ BM25 retrieval
   +
   local semantic retrieval
→ Reciprocal Rank Fusion
→ confidence assessment
→ abstain or continue
→ bounded history-aware ranking
→ source-backed strategy response
```

This is the final retrieval architecture used by the Hey Joey prototype.
