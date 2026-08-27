from app.context_builder import SyntheticContextBuilder
from rag.context_aware_strategy_service import build_context_aware_query


# Verify that personally identifying synthetic profile fields are omitted before
# context is exposed to the retrieval layer.
def test_sensitive_fields_are_excluded() -> None:
    # Build context for a sensory-related question using the production context selector.
    selection = SyntheticContextBuilder().build('What could help with loud classroom noise?')
    # Lowercase once so the privacy assertions are case-insensitive and deterministic.
    context = selection.context_text.lower()
    assert 'alex carter' not in context
    assert 'parent@example.com' not in context
    assert '2014-05-12' not in context
    assert '27 example street' not in context
    assert 'name' in selection.omitted_sensitive_fields
    assert 'email' in selection.omitted_sensitive_fields
    assert 'date_of_birth' in selection.omitted_sensitive_fields


# Confirm that a sensory query selects noise-related history while excluding
# unrelated sleep context.
def test_sensory_question_selects_relevant_context() -> None:
    selection = SyntheticContextBuilder().build('What could help with loud classroom noise?')
    context = selection.context_text.lower()
    assert 'unexpected or sustained noise' in context
    assert 'covered their ears' in context
    assert 'planned quiet-space routine' in context
    assert 'poor sleep quality' not in context


# Confirm that a sleep-focused query selects sleep-related history and does not
# pull in unrelated classroom-noise context.
def test_sleep_question_selects_sleep_context() -> None:
    selection = SyntheticContextBuilder().build('What might support a calmer bedtime after poor sleep?')
    context = selection.context_text.lower()
    assert 'sleep quality & duration' in context
    assert 'poor sleep quality' in context
    assert 'noisy classroom activity' not in context


# Verify that the final retrieval query preserves both the current question and
# the context selected by the builder.
def test_context_query_contains_question_and_context() -> None:
    # Reuse one builder instance to make the query-construction path explicit.
    builder = SyntheticContextBuilder()
    question = 'What could help with loud classroom noise?'
    selection = builder.build(question)
    # Exercise the same query-composition helper used by the context-aware service.
    query = build_context_aware_query(question, selection)
    assert question in query
    assert selection.context_text in query


def main() -> None:
    # Keep the standalone regression functions in a fixed order for predictable
    # local and CI output.
    tests = [
        test_sensitive_fields_are_excluded,
        test_sensory_question_selects_relevant_context,
        test_sleep_question_selects_sleep_context,
        test_context_query_contains_question_and_context,
    ]
    # Any failed assertion stops the script with a non-zero exit status for CI.
    for test in tests:
        test()
        print(f'PASS: {test.__name__}')
    print('\n4/4 synthetic context-builder tests passed.')


# Run the context-builder regression checks only when this module is executed directly.
if __name__ == '__main__':
    main()
