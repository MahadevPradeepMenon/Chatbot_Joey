from pprint import pprint

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)


def show_record(session: JoeyConversationSession) -> None:
    record = session.current_record

    print("\nCURRENT DRAFT")
    print("=" * 60)
    print(f"Summary: {record.summary}")
    print(f"Anxiety: {record.anxiety_level.value}")
    print(f"Mood zone: {record.mood_zone.value}")
    print(f"Mood labels: {record.mood_labels or ['Not detected']}")
    print(f"Behaviours: {record.behaviours or ['Not detected']}")
    print(f"Activity: {record.activity or 'Not detected'}")
    print(f"Environment: {record.environment or 'Not detected'}")
    print(
        "Possible triggers: "
        f"{record.possible_triggers or ['Not detected']}"
    )


def main() -> None:
    print("\nHEY JOEY MULTI-TURN DATA INPUT")
    print("=" * 60)

    note = input("Parent/carer note: ").strip()
    session = JoeyConversationSession.start(note)
    show_record(session)

    while session.status == ConversationStatus.collecting_information:
        print(f"\nJoey: {session.follow_up_question}")
        answer = input("Parent/carer: ").strip()

        try:
            session.submit_answer(answer)
        except ValueError as error:
            print(f"\nPlease try again: {error}")
            continue

        show_record(session)

    print("\nREADY FOR REVIEW")
    print("=" * 60)
    pprint(session.to_dict())

    decision = input(
        "\nConfirm this draft? yes/no: "
    ).strip().lower()

    if decision in {"yes", "y"}:
        session.confirm()
        print("\nDraft confirmed. It has not been written to storage yet.")
    else:
        session.reject()
        print("\nDraft rejected. Nothing was saved.")


if __name__ == "__main__":
    main()
