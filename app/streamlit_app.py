from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from app.conversation_manager import (
    ConversationStatus,
    JoeyConversationSession,
)
from app.extractor import extract_structured_record
from rag.history_aware_strategy_service import (
    HistoryAwareStrategyService,
)
from safety.safety_guard import should_limit_strategy_suggestions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = PROJECT_ROOT / "assets" / "hey_joey_logo.png"
LOCAL_OUTPUT_DIR = PROJECT_ROOT / "data" / "local"
CONFIRMED_RECORDS_FILE = (
    LOCAL_OUTPUT_DIR / "confirmed_joey_records.jsonl"
)


st.set_page_config(
    page_title="Hey Joey",
    page_icon=str(LOGO_PATH),
    layout="centered",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
        .stApp {
            background: #ffffff;
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background: #ffffff;
        }

        .block-container {
            max-width: 820px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        #MainMenu,
        footer {
            visibility: hidden;
            height: 0;
        }

        div[role="radiogroup"] {
            display: flex;
            justify-content: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }

        div[role="radiogroup"] label {
            background: white;
            border: 1px solid #d9e1db;
            border-radius: 999px;
            padding: 0.65rem 1.05rem;
        }

        div[role="radiogroup"] label:has(input:checked) {
            background: #126b57;
            border-color: #126b57;
        }

        div[role="radiogroup"] label:has(input:checked),
        div[role="radiogroup"] label:has(input:checked) p,
        div[role="radiogroup"] label:has(input:checked) span {
            color: #ffffff !important;
        }
        
        div[data-baseweb="textarea"] textarea {
            border-radius: 16px;
            min-height: 130px;
            background: white;
        }

        div.stButton > button {
            width: 100%;
            border-radius: 14px;
            min-height: 2.9rem;
            background: #126b57;
            color: white;
            border: 1px solid #126b57;
            font-weight: 700;
        }

        div.stButton > button:hover {
            background: #0b5747;
            border-color: #0b5747;
            color: white;
        }

        .joey-response {
            background: white;
            border: 1px solid #dfe5de;
            border-radius: 20px;
            padding: 1.25rem 1.35rem;
            margin-top: 1rem;
            line-height: 1.62;
            box-shadow: 0 6px 20px rgba(20, 55, 43, 0.04);
        }

        .joey-response strong {
            color: #0b5747;
        }

        .joey-strategy {
            margin-top: 0.9rem;
            padding-top: 0.9rem;
            border-top: 1px solid #edf0ed;
        }

        .joey-source {
            color: #68746e;
            font-size: 0.88rem;
            margin-top: 0.3rem;
        }

        .joey-heading {
            text-align: center;
            margin-bottom: 1.4rem;
        }

        .joey-heading h1 {
            margin-bottom: 0.25rem;
            color: #17211d;
        }

        .joey-heading p {
            color: #68746e;
            margin: 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_strategy_service() -> HistoryAwareStrategyService:
    """Load the local context-aware Hybrid RAG service once."""

    return HistoryAwareStrategyService()


def initialise_state() -> None:
    defaults: dict[str, Any] = {
        "record_session": None,
        "record_response": (
            "Tell me what happened in your own words. "
            "I will turn it into a journal draft and ask only "
            "for details that are still needed."
        ),
        "strategy_response": (
            "Ask what support strategy may be relevant. "
            "I will search the approved local Hey Joey strategy library."
        ),
        "last_mode": "Record what happened",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_confirmed_session(
    session: JoeyConversationSession,
) -> None:
    """Write a confirmed record locally in the background."""

    if session.status != ConversationStatus.confirmed:
        raise ValueError("The draft has not been confirmed.")

    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    saved_item = {
        "saved_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "source": "minimal_streamlit_interface",
        "original_note": session.original_note,
        "conversation_history": [
            {
                "question": turn.question,
                "answer": turn.answer,
                "field_name": turn.field_name,
            }
            for turn in session.history
        ],
        "structured_record": (
            session.current_record.model_dump(mode="json")
        ),
    }

    with CONFIRMED_RECORDS_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                saved_item,
                ensure_ascii=False,
            )
            + "\n"
        )


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def readable_list(values: list[str]) -> str:
    clean_values = [clean_text(value) for value in values]
    clean_values = [value for value in clean_values if value]

    if not clean_values:
        return ""

    if len(clean_values) == 1:
        return clean_values[0]

    if len(clean_values) == 2:
        return f"{clean_values[0]} and {clean_values[1]}"

    return (
        ", ".join(clean_values[:-1])
        + f", and {clean_values[-1]}"
    )


def build_record_summary(
    session: JoeyConversationSession,
) -> str:
    """Create a concise parent-facing summary of the hidden draft."""

    record = session.current_record
    details: list[str] = []

    if record.anxiety_level.value != "Unknown":
        details.append(
            f"anxiety was recorded as {record.anxiety_level.value.lower()}"
        )

    if record.mood_zone.value != "Unknown":
        details.append(
            f"the mood zone was recorded as {record.mood_zone.value}"
        )

    if record.environment:
        details.append(
            f"the setting was {record.environment}"
        )

    if record.possible_triggers:
        details.append(
            "possible triggers included "
            + readable_list(record.possible_triggers)
        )

    if details:
        understood = (
            "I have updated the same journal draft: "
            + "; ".join(details)
            + "."
        )
    else:
        understood = (
            "I have started a journal draft from what you described."
        )

    return understood


def build_ready_for_review_response(
    session: JoeyConversationSession,
) -> str:
    record = session.current_record
    parts = [
        build_record_summary(session),
    ]

    if record.summary:
        parts.append(
            f"My summary is: {record.summary}"
        )

    if record.risk_flags:
        parts.append(
            "I also noticed information that may need safety-aware review."
        )

    parts.append(
        "Reply <strong>yes</strong> to confirm and save it, "
        "or <strong>no</strong> to discard it."
    )

    return " ".join(parts)


def handle_record_input(user_text: str) -> str:
    """Run the entire multi-turn record workflow behind one text box."""

    command = clean_text(user_text)
    session: JoeyConversationSession | None = (
        st.session_state.record_session
    )

    if command.lower() in {"start over", "restart", "reset"}:
        st.session_state.record_session = None
        return (
            "Started over. Tell me what happened in your own words."
        )

    if session is None:
        session = JoeyConversationSession.start(command)
        st.session_state.record_session = session

        response = build_record_summary(session)

        if should_limit_strategy_suggestions(
            session.current_record
        ):
            response += (
                " I noticed a possible safety concern. "
                "Please make sure the child is safe and seek appropriate "
                "urgent or professional support when needed."
            )

        if (
            session.status
            == ConversationStatus.collecting_information
        ):
            response += (
                " " + str(session.follow_up_question)
            )
        else:
            response += (
                " " + build_ready_for_review_response(session)
            )

        return response

    if session.status == ConversationStatus.collecting_information:
        session.submit_answer(command)
        st.session_state.record_session = session

        if (
            session.status
            == ConversationStatus.collecting_information
        ):
            return (
                build_record_summary(session)
                + " "
                + str(session.follow_up_question)
            )

        return build_ready_for_review_response(session)

    if session.status == ConversationStatus.ready_for_review:
        answer = command.lower()

        if answer in {"yes", "y", "confirm", "save"}:
            session.confirm()
            save_confirmed_session(session)
            st.session_state.record_session = None
            return (
                "The journal entry has been confirmed and recorded. "
                "Its structured fields are now available in the background "
                "for the Journal Entries and Insights integration layer. "
                "You can describe another event whenever you are ready."
            )

        if answer in {"no", "n", "discard", "reject"}:
            session.reject()
            st.session_state.record_session = None
            return (
                "The draft was discarded and nothing was saved. "
                "You can describe another event whenever you are ready."
            )

        return (
            "Please reply <strong>yes</strong> to confirm and save the "
            "draft, or <strong>no</strong> to discard it."
        )

    st.session_state.record_session = None
    return "Tell me what happened and I will start a new journal draft."


def clean_strategy_title(title: str | None) -> str:
    title = clean_text(title)

    return re.sub(
        r"\s*\(Ages?[^)]*\)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()


def build_strategy_response(question: str) -> str:
    """Return only a readable answer and strategy options."""

    screening_record = extract_structured_record(question)

    if should_limit_strategy_suggestions(screening_record):
        return (
            "What you described may involve an immediate safety or injury "
            "concern. I will not provide ordinary strategy suggestions for "
            "that situation. Please make sure the child is safe and seek "
            "appropriate urgent or professional support."
        )

    service = get_strategy_service()
    result = service.retrieve(
        question=question,
        top_k=3,
        candidate_pool=6,
    )

    if not result.evidence:
        return (
            "I could not find a sufficiently relevant strategy in the "
            "current approved local collection."
        )

    titles = [
        clean_strategy_title(item.strategy_title)
        for item in result.evidence
    ]

    response_parts = [
        (
            "Based on what you asked and the relevant confirmed "
            "background available to this prototype, the strongest "
            "source-backed options focus on "
            f"{readable_list(titles)}."
        )
    ]

    if any(
        "already recorded as active"
        in item.history_note.lower()
        for item in result.evidence
    ):
        response_parts.append(
            "One of these options is already recorded as active, "
            "so reviewing how it is currently being used may be useful."
        )

    if any(
        (
            "helped somewhat" in item.history_note.lower()
            or "worked well" in item.history_note.lower()
        )
        for item in result.evidence
    ):
        response_parts.append(
            "Previous confirmed feedback also indicates that at least "
            "one related approach was reported to help."
        )

    strategy_html: list[str] = []

    for index, item in enumerate(
        result.evidence,
        start=1,
    ):
        title = (
            f"{item.strategy_code}: "
            f"{item.strategy_title}"
            if item.strategy_code
            else (
                item.strategy_title
                or "Relevant support strategy"
            )
        )

        passage = clean_text(item.passage)
        passage_preview = (
            passage
            if len(passage) <= 360
            else (
                passage[:360].rsplit(" ", maxsplit=1)[0]
                + "..."
            )
        )

        history_sentence = ""
        if "new strategy option" not in item.history_note.lower():
            history_sentence = (
                f"<br><em>{html.escape(item.history_note)}</em>"
            )

        strategy_html.append(
            '<div class="joey-strategy">'
            f"<strong>{index}. {html.escape(title)}</strong><br>"
            f"{html.escape(passage_preview)}"
            f"{history_sentence}"
            '<div class="joey-source">'
            f"Source: {html.escape(item.collection_title)}"
            "</div>"
            "</div>"
        )

    response_parts.append(
        "These are support options for parent or carer review, "
        "not a diagnosis or medical recommendation."
    )

    return (
        "<p>"
        + " ".join(
            html.escape(part)
            for part in response_parts
        )
        + "</p>"
        + "".join(strategy_html)
    )


def render_response(response: str) -> None:
    st.markdown(
        f'<div class="joey-response">{response}</div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    initialise_state()

    left_space, logo_column, title_column, right_space = st.columns(
    [1.5, 0.7, 2.4, 1.5]
)

    with logo_column:
        st.image(
        str(LOGO_PATH),
        width=82,
    )

    with title_column:
        st.markdown(
        """
        <div style="padding-top: 8px;">
            <h1 style="
                margin: 0;
                color: #116b57;
            ">
                Hey Joey
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
    """
    <p style="
        text-align: center;
        color: #68746e;
        margin-top: 0.2rem;
        margin-bottom: 1.4rem;
    ">
        Record an observation or ask for a support strategy.
    </p>
    """,
    unsafe_allow_html=True,
)

    mode = st.radio(
        "Choose a workflow",
        [
            "Record what happened",
            "Ask for a strategy",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode != st.session_state.last_mode:
        st.session_state.last_mode = mode

    current_response = (
        st.session_state.record_response
        if mode == "Record what happened"
        else st.session_state.strategy_response
    )

    render_response(current_response)

    with st.form(
        f"minimal_input_form_{mode}",
        clear_on_submit=True,
    ):
        user_text = st.text_area(
            "Message",
            placeholder=(
                "Describe what happened..."
                if mode == "Record what happened"
                else "Ask which strategy may help..."
            ),
            label_visibility="collapsed",
        )

        submitted = st.form_submit_button(
            "Send",
            type="primary",
            width="stretch",
        )

    if submitted:
        clean_input = clean_text(
            str(user_text or "")
        )

        if not clean_input:
            st.warning("Please type a message.")
            return

        try:
            if mode == "Record what happened":
                st.session_state.record_response = (
                    handle_record_input(clean_input)
                )
            else:
                with st.spinner(
                    "Searching the approved local strategy library..."
                ):
                    st.session_state.strategy_response = (
                        build_strategy_response(clean_input)
                    )

            st.rerun()

        except (ValueError, RuntimeError) as error:
            if mode == "Record what happened":
                st.session_state.record_response = (
                    f"I could not use that answer yet: "
                    f"{html.escape(str(error))}"
                )
            else:
                st.session_state.strategy_response = (
                    "I could not complete the strategy search: "
                    f"{html.escape(str(error))}"
                )

            st.rerun()


if __name__ == "__main__":
    main()
