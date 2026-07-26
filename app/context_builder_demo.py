from rag.context_aware_strategy_service import ContextAwareStrategyService


def preview(text: str, maximum: int = 260) -> str:
    clean = ' '.join(text.split())
    return clean if len(clean) <= maximum else clean[:maximum].rsplit(' ', maxsplit=1)[0] + '...'


def main() -> None:
    print('\nHEY JOEY SYNTHETIC CONTEXT DEMO')
    print('=' * 70)
    question = input('Parent/carer strategy question: ').strip()
    response = ContextAwareStrategyService().retrieve(question=question, top_k=3)

    print('\nSELECTED PRIVACY-SAFE CONTEXT')
    print('=' * 70)
    print(response.context.context_text)

    print('\nOMITTED SENSITIVE FIELDS')
    print('=' * 70)
    for field_name in response.context.omitted_sensitive_fields:
        print(f'- {field_name}')

    print('\nCONTEXT-AWARE HYBRID RESULTS')
    print('=' * 70)
    for item in response.evidence:
        title = f'{item.strategy_code}: {item.strategy_title}' if item.strategy_code else item.strategy_title
        print('\n' + '-' * 70)
        print(f'Rank {item.rank} | Hybrid score: {item.score:.6f}')
        print(f'Strategy: {title}')
        print(f'Collection: {item.collection_title}')
        print(f'Source: {item.source_file}')
        print(f'Passage: {preview(item.passage)}')


if __name__ == '__main__':
    main()
