# Integrated Semantic End-to-End Evaluation

## Purpose

This evaluation tested the complete local Joey workflow:

1. Parent/carer observation
2. Rule-based structured extraction
3. Safety-sensitive content detection
4. Local semantic strategy retrieval
5. Source-backed parent response
6. Parent confirmation requirement

No records were saved during the automated evaluation.

## Test Cases

Seven synthetic cases were evaluated:

- sensory noise and classroom overwhelm
- sleep and bedtime anxiety
- social anxiety
- eating and mealtime challenges
- toilet training
- communication difficulties
- self-injury and safety-sensitive content

## Initial Evaluation

The initial run produced:

- Cases passed: 5/7
- Checks passed: 60/63

The evaluation identified two genuine weaknesses:

1. The toilet-training query did not retrieve the expected Toilet Training collection.
2. A description of repeated head-hitting was not recognised as self-injurious behaviour, so ordinary strategy retrieval was not limited.

## Corrective Changes

The following improvements were made:

- expanded self-injury pattern detection;
- added injury-concern detection;
- distinguished self-injurious behaviour from general aggression;
- added explicit toilet-training extraction signals;
- included the original parent note in the semantic retrieval query;
- preserved safety-first behaviour by blocking ordinary strategy retrieval for safety-sensitive records.

## Final Evaluation

After the corrections, the complete test suite produced:

- Cases passed: 7/7
- Checks passed: 63/63

The self-injury case correctly triggered safety-sensitive handling and returned no ordinary strategy recommendations.

The toilet-training case retrieved evidence from the appropriate collection.

## Interpretation

The integrated Joey MVP passed all seven predefined synthetic end-to-end test cases and all 63 functional checks.

These results demonstrate successful behaviour on the designed test suite. They do not establish clinical effectiveness, general accuracy or performance on all possible parent observations.

## Outputs

The evaluation generated:

- `semantic_end_to_end_results.json`
- `semantic_end_to_end_results.csv`

These files preserve the final case-level results, retrieved sources, strategy titles, similarity scores and individual check outcomes.