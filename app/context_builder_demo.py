from rag.context_aware_strategy_service import ContextAwareStrategyService


# Keep retrieved passages short enough for a readable command-line demo.
def preview(text: str, maximum: int = 260) -> str:
    # Collapse excess whitespace before applying the preview length limit.
    clean = ' '.join(text.split())
    # Truncate at the final complete word rather than cutting a word in half.
    return clean if len(clean) <= maximum else clean[:maximum].rsplit(' ', maxsplit=1)[0] + '...'


# This small CLI demonstrates how a parent/carer question is combined with
# selected historical context before context-aware hybrid retrieval.
def main() -> None:
    print('\nHEY JOEY SYNTHETIC CONTEXT DEMO')
    print('=' * 70)
    # Read one free-text strategy question directly from the command line.
    question = input('Parent/carer strategy question: ').strip()
    # Run the context-aware retrieval service and request the top three results.
    response = ContextAwareStrategyService().retrieve(question=question, top_k=3)

    print('\nSELECTED PRIVACY-SAFE CONTEXT')
    print('=' * 70)
    # Show only the context that the builder selected as relevant for this query.
    print(response.context.context_text)

    print('\nOMITTED SENSITIVE FIELDS')
    print('=' * 70)
    # Display the names of sensitive fields detected and omitted from context.
    for field_name in response.context.omitted_sensitive_fields:
        print(f'- {field_name}')

    print('\nCONTEXT-AWARE HYBRID RESULTS')
    print('=' * 70)
    # Print each retrieved evidence item with its rank, source and short passage.
    for item in response.evidence:
        # Include the strategy code when one is available; otherwise use the title alone.
        title = f'{item.strategy_code}: {item.strategy_title}' if item.strategy_code else item.strategy_title
        print('\n' + '-' * 70)
        print(f'Rank {item.rank} | Hybrid score: {item.score:.6f}')
        print(f'Strategy: {title}')
        print(f'Collection: {item.collection_title}')
        print(f'Source: {item.source_file}')
        print(f'Passage: {preview(item.passage)}')


# Run the demo only when this file is executed directly.
if __name__ == '__main__':
    main()

