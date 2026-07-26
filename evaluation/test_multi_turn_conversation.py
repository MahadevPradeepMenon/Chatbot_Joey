from requests import session

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)
from app.schemas import AnxietyLevel


def test_sensory_follow_up() -> None:
    session = JoeyConversationSession.start(
        "The classroom was loud and she covered her ears."
    )

    trigger_answer = (
        "The sound was sudden, very loud, "
        "and difficult to escape."
    )

    while (
        session.status
        == ConversationStatus.collecting_information
    ):
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


def test_environment_and_trigger_follow_up() -> None:
    session = JoeyConversationSession.start(
        "He seemed worried."
    )

    assert session.pending_field == "environment"

    session.submit_answer("It happened at school.")

    assert session.current_record.environment == "school"
    assert session.pending_field == "possible_triggers"

    session.submit_answer(
        "There was an unexpected timetable change."
    )

    assert session.current_record.possible_triggers
    assert session.status == ConversationStatus.ready_for_review


def test_confirmation_state() -> None:
    session = JoeyConversationSession.start(
        "She was calm at home after dinner."
    )

    while session.status == ConversationStatus.collecting_information:
        session.submit_answer("I don't know")

    session.confirm()

    assert session.status == ConversationStatus.confirmed


def main() -> None:
    tests = [
        test_sensory_follow_up,
        test_environment_and_trigger_follow_up,
        test_confirmation_state,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("\n3/3 multi-turn conversation tests passed.")


if __name__ == "__main__":
    main()
