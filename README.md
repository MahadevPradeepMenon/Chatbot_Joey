# Chatbot_Joey
RAG-based chatbot prototype for personalised Hey Joey insights and strategy guidance.

## Current MVP

Joey is a local conversational data-input and strategy-support prototype for the Hey Joey app.

The current system can:

- convert parent/carer free-text observations into structured records
- detect mood, anxiety, behaviours, possible triggers, and Quick Track fields
- ask a follow-up question
- retrieve relevant high-level strategy support
- apply medication and safety restrictions
- require parent/carer confirmation before saving
- run without a paid AI API

## System Pipeline

`Free-text note → rule-based extraction → structured record → local strategy retrieval → safety-aware response → parent confirmation`

## Evaluation

The baseline extractor was tested on 50 synthetic journal observations.

After rule refinement, unknown mood-zone classifications decreased from 31 to 0. Further review indicated that the improved extractor may classify some mild cases too strongly.

The complete MVP is also tested using synthetic end-to-end cases covering ordinary observations, sensory discomfort, medication mentions, safety concerns, and positive observations.

## Important Technical Status

The current strategy retriever is a local rule-based retrieval baseline.

It demonstrates a RAG-ready system architecture, but it is not yet a full embedding-based RAG implementation. Future work will use approved Hey Joey strategy documents and semantic retrieval.

## Safety and Privacy

- No automatic saving
- Parent/carer confirmation required
- No diagnosis
- No medication or dosage recommendations
- Safety-sensitive wording is prioritised
- Local manually entered records are excluded from Git
- Synthetic data is used for prototype evaluation

## Limitations

- Rule-based extraction depends on known wording
- Context and negation handling are limited
- Mood severity may be over-classified
- Strategy content is currently mock/high-level content
- Domain-expert evaluation is still required