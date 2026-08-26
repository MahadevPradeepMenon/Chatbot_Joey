from pprint import pprint

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)


# Display the current in-memory journal draft after each conversation turn.
def show_record(session: JoeyConversationSession) -> None:
    # Read the latest validated structured record held by the conversation session.
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


# This small CLI demonstrates the multi-turn journal workflow without any
# persistence layer or Streamlit/FastAPI interface.
def main() -> None:
    print("\nHEY JOEY MULTI-TURN DATA INPUT")
    print("=" * 60)

    # Start with one free-text parent/carer observation.
    note = input("Parent/carer note: ").strip()
    # Starting the session runs the extractor and selects the first follow-up
    # question when required information is still missing.
    session = JoeyConversationSession.start(note)
    show_record(session)

    # Continue asking one follow-up at a time until the session moves to the
    # review-ready state.
    while session.status == ConversationStatus.collecting_information:
        print(f"\nJoey: {session.follow_up_question}")
        answer = input("Parent/carer: ").strip()

        # Merge the answer into the structured draft; invalid answers are
        # reported and the same conversation can continue.
        try:
            session.submit_answer(answer)
        except ValueError as error:
            print(f"\nPlease try again: {error}")
            continue

        show_record(session)

    print("\nREADY FOR REVIEW")
    print("=" * 60)
    # Show the complete serialisable session state before the final decision.
    pprint(session.to_dict())

    decision = input(
        "\nConfirm this draft? yes/no: "
    ).strip().lower()

    # Confirmation changes only the in-memory workflow state in this demo;
    # no storage function is called here.
    if decision in {"yes", "y"}:
        session.confirm()
        print("\nDraft confirmed. It has not been written to storage yet.")
    else:
        # Any non-yes response rejects the in-memory draft without saving it.
        session.reject()
        print("\nDraft rejected. Nothing was saved.")


# Run the demo only when this file is executed directly.
if __name__ == "__main__":
    main()
