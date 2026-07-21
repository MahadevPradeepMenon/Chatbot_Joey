# Rule-Based and Semantic Retrieval Comparison

## Purpose

This evaluation compared the original rule-based Joey strategy retriever
with the new local semantic retriever.

The purpose was to determine whether semantic retrieval improved the
ranking and coverage of relevant Hey Joey strategy collections.

## Evaluation Dataset

Ten synthetic support queries were used, covering:

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

Each query contained predefined expected keywords used to identify
relevant strategy metadata within the top three results.

## Metrics

The evaluation measured:

- Hit@1
- Hit@3
- Mean Reciprocal Rank
- average retrieval latency
- retrieval errors

Hit@1 indicates whether the first result matched an expected support area.

Hit@3 indicates whether a matching result appeared within the first
three results.

Mean Reciprocal Rank rewards systems that place the first relevant result
nearer the top of the ranking.

## Results

### Rule-Based Baseline

- Hit@1: 3/10
- Hit@3: 5/10
- Mean Reciprocal Rank: 0.4000
- Average latency: 0.000493 seconds

### Semantic Retriever

- Hit@1: 8/10
- Hit@3: 9/10
- Mean Reciprocal Rank: 0.8333
- Average latency: 0.029215 seconds

## Interpretation

The semantic retriever substantially improved relevant-result ranking
and coverage compared with the rule-based baseline.

Hit@1 increased from 3/10 to 8/10, while Hit@3 increased from 5/10 to
9/10. Mean Reciprocal Rank increased from 0.4000 to 0.8333.

The semantic retriever introduced additional computational latency.
However, after model warm-up, its average retrieval time was
approximately 29 milliseconds per query.

The rule-based retriever remained substantially faster but retrieved
the expected support area less consistently.

## Limitations

The evaluation used only ten designed synthetic queries.

Relevance was assessed through predefined keyword matching against
retrieval metadata rather than independent human expert judgements.

The results therefore demonstrate comparative performance on this
evaluation set and do not establish universal retrieval accuracy,
clinical effectiveness or suitability for unsupervised decision-making.

## Conclusion

For the designed test set, the local semantic retriever provided better
retrieval quality than the original rule-based baseline while maintaining
practical local response times and requiring no paid language-model API.