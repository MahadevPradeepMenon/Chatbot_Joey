import sys
from enum import Enum
from pathlib import Path
from typing import Any

import streamlit as st


# Ensure project-root imports work when Streamlit runs this file.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.extractor import extract_structured_record
from app.joey_cli import (
    CONFIRMED_RECORDS_FILE,
    save_confirmed_record,
)
from app.response_builder import build_parent_response
from app.schemas import StructuredJoeyRecord
from rag.joey_strategy_service import (
    JoeyStrategyEvidence,
    JoeyStrategyService,
)
from safety.safety_guard import (
    build_safety_notice,
    should_limit_strategy_suggestions,
)


st.set_page_config(
    page_title="Hey Joey",
    page_icon="💬",
    layout="wide",
)


@st.cache_resource
def load_strategy_service() -> JoeyStrategyService:
    """
    Load the embedding model and semantic index once.

    Streamlit reruns the page after interactions, so the service is
    cached to avoid repeatedly loading the local model.
    """

    return JoeyStrategyService()


def initialise_session_state() -> None:
    """Create the state used across Streamlit reruns."""

    defaults: dict[str, Any] = {
        "analysed_note": "",
        "record": None,
        "strategies": [],
        "parent_response": "",
        "retrieval_error": "",
        "save_status": "",
        "record_saved": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_analysis() -> None:
    """
    Remove the current analysis while leaving the note available
    for the parent or carer to rewrite.
    """

    st.session_state.analysed_note = ""
    st.session_state.record = None
    st.session_state.strategies = []
    st.session_state.parent_response = ""
    st.session_state.retrieval_error = ""
    st.session_state.save_status = ""
    st.session_state.record_saved = False


def clear_everything() -> None:
    """Clear the note and all generated results."""

    reset_analysis()
    st.session_state.note_input = ""


def display_value(value: Any) -> str:
    """Convert schema enums and ordinary values into readable text."""

    if isinstance(value, Enum):
        return str(value.value)

    if value is None or value == "":
        return "Not detected"

    return str(value)


def display_list(items: list[str]) -> str:
    """Format a record list for the interface."""

    if not items:
        return "None detected"

    return ", ".join(items)


def analyse_note(note: str) -> None:
    """Run the complete Joey workflow without saving anything."""

    clean_note = " ".join(note.split()).strip()

    if not clean_note:
        st.session_state.retrieval_error = (
            "Please enter a parent or carer observation."
        )
        return

    record = extract_structured_record(clean_note)

    strategies: list[JoeyStrategyEvidence] = []
    retrieval_error = ""

    if not should_limit_strategy_suggestions(record):
        try:
            strategy_service = load_strategy_service()

            strategies = strategy_service.retrieve_for_record(
                record,
                original_note=clean_note,
                top_k=3,
            )

        except Exception as error:
            retrieval_error = (
                "Joey created the structured record, but the local "
                f"strategy system could not be loaded: {error}"
            )

    parent_response = build_parent_response(
        original_note=clean_note,
        record=record,
        retrieved_strategies=strategies,
    )

    st.session_state.analysed_note = clean_note
    st.session_state.record = record
    st.session_state.strategies = strategies
    st.session_state.parent_response = parent_response
    st.session_state.retrieval_error = retrieval_error
    st.session_state.save_status = ""
    st.session_state.record_saved = False


def display_structured_record(
    record: StructuredJoeyRecord,
) -> None:
    """Display the extracted Joey record in parent-friendly sections."""

    st.subheader("Structured observation")

    left_column, right_column = st.columns(2)

    with left_column:
        st.markdown("**Summary**")
        st.write(record.summary)

        st.markdown("**Mood and anxiety**")
        st.write(
            f"Mood zone: {display_value(record.mood_zone)}"
        )
        st.write(
            f"Anxiety level: "
            f"{display_value(record.anxiety_level)}"
        )

        st.markdown("**Behaviours and signals**")
        st.write(
            display_list(
                record.behaviours + record.mood_labels
            )
        )

    with right_column:
        st.markdown("**Possible triggers**")
        st.write(
            display_list(record.possible_triggers)
        )

        st.markdown("**Activity**")
        st.write(display_value(record.activity))

        st.markdown("**Environment**")
        st.write(display_value(record.environment))

        st.markdown("**Quick Track suggestions**")
        st.write(
            display_list(
                record.quick_track_suggestions
            )
        )

    st.markdown("**Joey's follow-up question**")

    st.info(
        record.follow_up_question
        or "Would you like to add more detail?"
    )

    with st.expander("View the complete structured record"):
        st.json(record.model_dump(mode="json"))


def strategy_heading(
    strategy: JoeyStrategyEvidence,
) -> str:
    """Build a strategy heading for the evidence panel."""

    if strategy.strategy_code and strategy.strategy_title:
        return (
            f"{strategy.rank}. "
            f"{strategy.strategy_code}: "
            f"{strategy.strategy_title}"
        )

    return (
        f"{strategy.rank}. "
        f"{strategy.strategy_title or 'Relevant support strategy'}"
    )


def display_strategy_evidence(
    strategies: list[JoeyStrategyEvidence],
) -> None:
    """Display retrieved passages and their source provenance."""

    st.subheader("Relevant source-backed strategies")

    if not strategies:
        st.info(
            "No ordinary strategy evidence was retrieved "
            "for this observation."
        )
        return

    for strategy in strategies:
        with st.expander(
            strategy_heading(strategy)
        ):
            st.markdown(
                f"**Collection:** "
                f"{strategy.collection_title}"
            )

            if strategy.theme:
                st.markdown(
                    f"**Theme:** {strategy.theme}"
                )

            st.markdown(
                f"**Source document:** "
                f"`{strategy.source_file}`"
            )

            st.markdown("**Relevant passage**")
            st.write(strategy.passage)

            st.caption(
                "Technical similarity score: "
                f"{strategy.score:.4f}. "
                "This is a ranking signal, not a probability "
                "or clinical confidence value."
            )


def display_confirmation_controls(
    note: str,
    record: StructuredJoeyRecord,
) -> None:
    """Display save, reject and rewrite controls."""

    st.subheader("Review and confirmation")

    st.write(
        "Joey has not saved this observation automatically. "
        "Review the information before deciding what to do."
    )

    save_column, reject_column, rewrite_column = st.columns(3)

    with save_column:
        save_clicked = st.button(
            "Save confirmed record",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.record_saved,
        )

        if save_clicked:
            save_confirmed_record(
                note,
                record,
            )

            st.session_state.record_saved = True
            st.session_state.save_status = (
                f"Saved locally to {CONFIRMED_RECORDS_FILE}"
            )

    with reject_column:
        reject_clicked = st.button(
            "Do not save",
            use_container_width=True,
        )

        if reject_clicked:
            st.session_state.save_status = (
                "The record was not saved."
            )

    with rewrite_column:
        st.button(
            "Rewrite note",
            use_container_width=True,
            on_click=reset_analysis,
        )

    if st.session_state.save_status:
        if st.session_state.record_saved:
            st.success(st.session_state.save_status)
        else:
            st.info(st.session_state.save_status)


def main() -> None:
    """Render the Hey Joey Streamlit interface."""

    initialise_session_state()

    st.title("Hey Joey")
    st.caption(
        "Local conversational data input and "
        "source-backed strategy retrieval"
    )

    st.warning(
        "Joey is a support tool. It does not diagnose, provide "
        "medical treatment or replace professional advice."
    )

    with st.sidebar:
        st.header("System status")

        st.write("Local processing")
        st.write("10 approved strategy documents")
        st.write("359 searchable passages")
        st.write("No paid language-model API")

        st.divider()

        st.button(
            "Clear current session",
            on_click=clear_everything,
            use_container_width=True,
        )

    st.subheader("Parent or carer observation")

    note = st.text_area(
        "Describe what happened",
        key="note_input",
        height=170,
        placeholder=(
            "Example: My child covered their ears and wanted "
            "to leave when the classroom became noisy."
        ),
        help=(
            "Joey will structure the observation and retrieve "
            "relevant local strategy evidence."
        ),
    )

    analyse_clicked = st.button(
        "Analyse observation",
        type="primary",
        use_container_width=True,
    )

    if analyse_clicked:
        with st.spinner(
            "Analysing the observation and searching "
            "the local strategy library..."
        ):
            analyse_note(note)

    if (
        st.session_state.retrieval_error
        and st.session_state.record is None
    ):
        st.error(st.session_state.retrieval_error)

    record = st.session_state.record

    if record is None:
        return

    st.divider()

    safety_notice = build_safety_notice(record)

    if safety_notice:
        st.error(safety_notice)

    display_structured_record(record)

    st.divider()

    if should_limit_strategy_suggestions(record):
        st.warning(
            "Ordinary strategy retrieval was limited because "
            "this observation may involve a safety concern."
        )
    else:
        if st.session_state.retrieval_error:
            st.warning(
                st.session_state.retrieval_error
            )

        display_strategy_evidence(
            st.session_state.strategies
        )

    st.divider()

    st.subheader("Joey response")

    st.text_area(
        "Generated parent-facing response",
        value=st.session_state.parent_response,
        height=430,
        disabled=True,
    )

    st.divider()

    display_confirmation_controls(
        st.session_state.analysed_note,
        record,
    )


if __name__ == "__main__":
    main()