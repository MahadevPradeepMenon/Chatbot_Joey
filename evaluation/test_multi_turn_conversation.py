from requests import session

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)
from app.schemas import AnxietyLevel


# Exercise a multi-turn sensory scenario in which the conversation manager asks
# follow-up questions until the draft has enough information for review.
def test_sensory_follow_up() -> None:
    session = JoeyConversationSession.start(
        "The classroom was loud and she covered her ears."
    )

    # Reuse a specific trigger description when the pending field requests details
    # about what may have caused the distress.
    trigger_answer = (
        "The sound was sudden, very loud, "
        "and difficult to escape."
    )

    # Continue answering the manager's requested fields until collection is complete.
    while (
        session.status
        == ConversationStatus.collecting_information
    ):
        # Supply field-specific answers where the regression needs to verify parsing;
        # all other requested fields receive the neutral "I don't know" response.
        if session.pending_field == "possible_triggers":
            session.submit_answer(trigger_answer)

        elif session.pending_field == "anxiety_level":
            session.submit_answer("High")

        else:
            session.submit_answer("I don't know")

    assert (
        session.current_record.anxiety_level
        == AnxietyLevel.high
    )

    # Confirm that the submitted trigger wording survives in the structured record
    # rather than being lost during the multi-turn update cycle.
    assert any(
        "sudden" in trigger.lower()
        and "difficult to escape" in trigger.lower()
        for trigger
        in session.current_record.possible_triggers
    )

    assert (
        session.status
        == ConversationStatus.ready_for_review
    )


# Verify the expected follow-up sequence for an initially vague observation:
# environment first, then possible trigger information.
def test_environment_and_trigger_follow_up() -> None:
    session = JoeyConversationSession.start(
        "He seemed worried."
    )

    assert session.pending_field == "environment"

    # The environment answer should update the record and advance the pending field.
    session.submit_answer("It happened at school.")

    assert session.current_record.environment == "school"
    assert session.pending_field == "possible_triggers"

    # A concrete trigger answer should populate possible_triggers and complete the
    # remaining information needed for review.
    session.submit_answer(
        "There was an unexpected timetable change."
    )

    assert session.current_record.possible_triggers
    assert session.status == ConversationStatus.ready_for_review


# Verify the final workflow transition from information collection to explicit
# parent confirmation.
def test_confirmation_state() -> None:
    session = JoeyConversationSession.start(
        "She was calm at home after dinner."
    )

    # Use neutral answers to finish any outstanding follow-ups without introducing
    # extra scenario-specific information.
    while session.status == ConversationStatus.collecting_information:
        session.submit_answer("I don't know")

    # Confirmation should move a review-ready session into the final confirmed state.
    session.confirm()

    assert session.status == ConversationStatus.confirmed


def main() -> None:
    # Keep the three regression scenarios in a fixed order for deterministic local
    # and CI output.
    tests = [
        test_sensory_follow_up,
        test_environment_and_trigger_follow_up,
        test_confirmation_state,
    ]

    # Any failed assertion stops the module with a non-zero exit status for CI.
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("\n3/3 multi-turn conversation tests passed.")


# Run the multi-turn conversation regressions only when executed directly.
if __name__ == "__main__":
    main()

