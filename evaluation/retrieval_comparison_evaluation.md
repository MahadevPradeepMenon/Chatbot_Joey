# Development Retrieval Comparison: Rule-Based, Semantic and Hybrid


> **Status note:** This document records an earlier **10-query development evaluation** retained as supporting engineering evidence. It is **not** the final MSc dissertation retrieval experiment. The final thesis evaluation uses **30 synthetic queries** and compares **Rule-based, BM25-only, Semantic-only and Hybrid RRF** retrieval. The final datasets, runner and results are stored under `evaluation/final_thesis/`.

## Purpose

This development evaluation compared three local Joey strategy-retrieval methods:

1. the original deterministic rule-based retriever;
2. the local semantic retriever;
3. the Hybrid retriever, which combines semantic and BM25 rankings using Reciprocal Rank Fusion.

The purpose was to determine how the three methods differed in relevant-result ranking, top-three coverage, retrieval latency and execution reliability.

## Evaluation Dataset

Ten synthetic support queries were used for this development comparison, covering:

- friendship
- toilet training
- sensory processing
- behavioural and emotional regulation
- crisis management
- hygiene
- sleep and bedtime
- eating and mealtime
- communication
- social anxiety

Each query contained predefined expected keywords used to identify relevant strategy metadata within the top three results.

All three retrievers were evaluated on the same queries, expected keywords and `top_k = 3` setting.


For the final dissertation experiment, the evaluation was expanded to 30 synthetic queries across the same ten strategy collections and a separate BM25-only method was added. Those final artefacts are stored under `evaluation/final_thesis/`.

## Retrieval Methods

### Rule-Based Baseline

The rule-based baseline used deterministic extraction and category-matching logic to select locally stored Hey Joey strategies.

### Semantic Retriever

The semantic retriever used local sentence embeddings to rank strategies according to semantic similarity with the structured retrieval query.

### Hybrid Retriever

The Hybrid retriever combined:

- local semantic retrieval;
- local BM25 lexical retrieval;
- Reciprocal Rank Fusion.

The Hybrid method therefore considered both semantic similarity and direct keyword overlap before producing the final ranking.

## Metrics

The evaluation measured:

- Hit@1
- Hit@3
- Mean Reciprocal Rank
- average retrieval latency
- retrieval errors

Hit@1 indicates whether the first result matched an expected support area.

Hit@3 indicates whether a matching result appeared within the first three results.

Mean Reciprocal Rank rewards systems that place the first relevant result nearer the top of the ranking.

Average latency was measured after the local retrieval components had been loaded and warmed up.

## Results

| Retriever | Hit@1 | Hit@3 | Mean Reciprocal Rank | Average latency | Errors |
|---|---:|---:|---:|---:|---:|
| Rule-based | 3/10 | 5/10 | 0.4000 | 0.000938 seconds | 0 |
| Semantic | 8/10 | 9/10 | 0.8333 | 0.065338 seconds | 0 |
| Hybrid | 7/10 | 9/10 | 0.8000 | 0.064551 seconds | 0 |


## Relationship to the Final Thesis Evaluation

The results above are preserved as an earlier development benchmark. They should not be used as the source for the final dissertation retrieval metrics.

The final thesis experiment used 30 synthetic queries and four retrieval methods:

| Retriever | Hit@1 | Hit@3 | MRR | Mean warm-run latency |
|---|---:|---:|---:|---:|
| Rule-based baseline | 40.0% | 50.0% | 0.4500 | 0.615 ms |
| BM25-only | 66.7% | 86.7% | 0.7611 | 4.316 ms |
| Semantic-only | 86.7% | 90.0% | 0.8833 | 28.765 ms |
| Hybrid RRF | 86.7% | 90.0% | 0.8833 | 30.142 ms |

Semantic-only and Hybrid RRF tied on the final synthetic ranking metrics. Hybrid RRF remained the application default because it combines lexical and semantic evidence while keeping the two ranking signals separate until Reciprocal Rank Fusion.

The canonical final thesis artefacts are:

- `evaluation/final_thesis/data/retrieval_final_cases.json`
- `evaluation/final_thesis/results/retrieval_final_case_results.csv`
- `evaluation/final_thesis/results/retrieval_final_summary.csv`
- `evaluation/final_thesis/results/retrieval_final_results.json`
- `evaluation/final_thesis/run_final_ml_experiments.py`

## Interpretation

Both embedding-based approaches substantially outperformed the original rule-based baseline on the designed ten-case evaluation set.

The semantic retriever achieved the strongest overall ranking performance:

- Hit@1 increased from 3/10 for the rule-based baseline to 8/10;
- Hit@3 increased from 5/10 to 9/10;
- Mean Reciprocal Rank increased from 0.4000 to 0.8333.

The Hybrid retriever also performed substantially better than the rule-based baseline:

- Hit@1 was 7/10;
- Hit@3 was 9/10;
- Mean Reciprocal Rank was 0.8000.

Semantic retrieval therefore placed the expected support area at rank one more often than Hybrid retrieval on this test set. However, both methods achieved the same top-three coverage of 9/10.

The Hybrid method did not automatically outperform semantic-only retrieval. Reciprocal Rank Fusion can promote strategies that score strongly in both semantic and lexical retrieval, but this may also move an otherwise relevant semantic result from first to second position. This result demonstrates why Hybrid RAG should be evaluated rather than assumed to be superior.

The rule-based retriever remained substantially faster, with an average latency below one millisecond. The semantic and Hybrid retrievers averaged approximately 65 milliseconds per query after warm-up, which remained practical for this local prototype.

All three retrieval methods completed the ten evaluation cases without execution errors.

## Limitations

The evaluation used only ten designed synthetic queries.

Relevance was assessed through predefined keyword matching against retrieval metadata rather than independent human expert judgements.

The test set may favour some retrieval behaviours over others and does not measure every possible advantage of lexical-semantic fusion.

Latency measurements depend on the local machine, operating environment, model state and file-system performance. They should therefore be treated as indicative rather than universal benchmarks.

The results demonstrate comparative retrieval performance on this evaluation set only. They do not establish universal retrieval accuracy, clinical effectiveness or suitability for unsupervised decision-making.

## Conclusion

For this designed ten-case development evaluation set, semantic-only retrieval achieved the strongest ranking performance, with Hit@1 of 8/10, Hit@3 of 9/10 and Mean Reciprocal Rank of 0.8333.

Hybrid BM25 and semantic retrieval achieved Hit@1 of 7/10, Hit@3 of 9/10 and Mean Reciprocal Rank of 0.8000. It therefore matched semantic retrieval for top-three coverage while performing slightly less strongly at rank one.

Both local embedding-based approaches substantially outperformed the original rule-based baseline, while maintaining practical local response times and requiring no paid language-model API.

The Hybrid retriever remained the application’s chosen production-style retrieval architecture because it combines semantic and lexical evidence. This ten-query development evaluation showed semantic-only retrieval performing best on that particular test set; the later 30-query final thesis experiment found Semantic-only and Hybrid RRF tied on Hit@1, Hit@3 and MRR.
