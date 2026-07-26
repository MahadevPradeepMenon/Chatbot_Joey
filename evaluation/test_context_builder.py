from app.context_builder import SyntheticContextBuilder
from rag.context_aware_strategy_service import build_context_aware_query


def test_sensitive_fields_are_excluded() -> None:
    selection = SyntheticContextBuilder().build('What could help with loud classroom noise?')
    context = selection.context_text.lower()
    assert 'alex carter' not in context
    assert 'parent@example.com' not in context
    assert '2014-05-12' not in context
    assert '27 example street' not in context
    assert 'name' in selection.omitted_sensitive_fields
    assert 'email' in selection.omitted_sensitive_fields
    assert 'date_of_birth' in selection.omitted_sensitive_fields


def test_sensory_question_selects_relevant_context() -> None:
    selection = SyntheticContextBuilder().build('What could help with loud classroom noise?')
    context = selection.context_text.lower()
    assert 'unexpected or sustained noise' in context
    assert 'covered their ears' in context
    assert 'planned quiet-space routine' in context
    assert 'poor sleep quality' not in context


def test_sleep_question_selects_sleep_context() -> None:
    selection = SyntheticContextBuilder().build('What might support a calmer bedtime after poor sleep?')
    context = selection.context_text.lower()
    assert 'sleep quality & duration' in context
    assert 'poor sleep quality' in context
    assert 'noisy classroom activity' not in context


def test_context_query_contains_question_and_context() -> None:
    builder = SyntheticContextBuilder()
    question = 'What could help with loud classroom noise?'
    selection = builder.build(question)
    query = build_context_aware_query(question, selection)
    assert question in query
    assert selection.context_text in query


def main() -> None:
    tests = [
        test_sensitive_fields_are_excluded,
        test_sensory_question_selects_relevant_context,
        test_sleep_question_selects_sleep_context,
        test_context_query_contains_question_and_context,
    ]
    for test in tests:
        test()
        print(f'PASS: {test.__name__}')
    print('\n4/4 synthetic context-builder tests passed.')


if __name__ == '__main__':
    main()
