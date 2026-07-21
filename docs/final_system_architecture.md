# Hey Joey Final System Architecture

## System Purpose

Hey Joey is a local-first conversational support prototype for parents
and carers of neurodivergent children.

The system converts a natural-language observation into a structured
record, retrieves relevant passages from approved Hey Joey strategy
documents and produces a cautious, source-backed response for the
parent or carer to review.

The system does not diagnose, prescribe treatment or save information
without confirmation.

## Final Processing Pipeline

```text
Parent/carer observation
        |
        v
Rule-based structured extraction
        |
        v
Safety and medication checks
        |
        +---------------- Safety concern detected ----------------+
        |                                                         |
        |                                                         v
        |                                              Safety-first response
        |                                              Ordinary retrieval blocked
        |
        v
Structured retrieval query
        |
        v
Local semantic embedding model
        |
        v
Search across local strategy embeddings
        |
        v
Rank and deduplicate strategy evidence
        |
        v
Source-backed parent response
        |
        v
Parent/carer review and confirmation
        |
        v
Optional local JSONL save