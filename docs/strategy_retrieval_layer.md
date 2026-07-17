# Joey Strategy Retrieval Layer

## Purpose

The strategy retrieval layer connects Joey's structured note extraction to relevant support categories.

This is the first step toward a retrieval-augmented generation system.

---

## Current Workflow

1. Parent/carer enters a free-text note.
2. Joey extracts a structured record.
3. The retrieval layer uses the structured fields to find relevant strategy support.
4. Joey displays the retrieved strategy categories, safe suggestions, and evidence.
5. The parent/carer confirms before anything is saved.

---

## Current Knowledge Base

The current knowledge base is stored in:

`data/processed/strategy_knowledge_base.json`

It contains high-level mock strategy entries for:

- sensory processing
- emotional regulation
- transitions and routines
- sleep and bedtime
- eating and mealtimes
- school routines
- crisis and safety

This avoids exposing private or proprietary Hey Joey strategy documents during early development.

---

## Retrieval Method

The current retriever is rule-based.

It scores strategy entries using:

- matched strategy categories
- matched keywords
- mood zone
- risk flags
- extracted triggers
- Quick Track suggestions

This is a local baseline retrieval method.

---

## Why This Is Not Final RAG Yet

This version does not use embeddings or a vector database.

It is still useful because it proves the system architecture:

`free-text note → structured extraction → retrieval → safe support`

Later, this can be upgraded to embedding-based retrieval using approved Hey Joey strategy documents.

---

## Safety Notes

Joey should:

- use retrieved strategies as support, not diagnosis
- avoid medical advice
- avoid claiming certainty
- ask for parent/carer confirmation
- escalate safety-related notes instead of treating them as ordinary strategy suggestions