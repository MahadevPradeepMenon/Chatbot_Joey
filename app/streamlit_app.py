from __future__ import annotations

import base64
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


def logo_data_uri() -> str:
    """Return the local logo as an embeddable data URI."""

    encoded = base64.b64encode(
        LOGO_PATH.read_bytes()
    ).decode("ascii")

    return f"data:image/png;base64,{encoded}"


st.set_page_config(
    page_title="Hey Joey",
    page_icon=str(LOGO_PATH),
    layout="centered",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
        :root {
            --joey-green: #126b57;
            --joey-green-dark: #0b5747;
            --joey-green-soft: #f4faf6;
            --joey-text: #17211d;
            --joey-muted: #68746e;
            --joey-border: #d9e1db;
            --joey-input: #f2f5f8;
        }

        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background: #ffffff;
        }

        .block-container {
            max-width: 900px;
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

        /* ---------------------------------------------------------
           Header
        --------------------------------------------------------- */

        .joey-header {
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 18px;
            margin: 0 auto 0.6rem auto;
        }

        .joey-header img {
            width: 96px;
            height: 96px;
            object-fit: contain;
            border-radius: 20px;
            display: block;
        }

        .joey-header h1 {
            margin: 0;
            color: var(--joey-green);
            font-size: 3rem;
            line-height: 1;
            font-weight: 760;
        }

        .joey-subtitle {
            text-align: center;
            color: var(--joey-muted);
            margin-top: 0.2rem;
            margin-bottom: 1.4rem;
            font-size: 1rem;
        }

        /* ---------------------------------------------------------
           Segmented workflow selector
        --------------------------------------------------------- */

        .stButtonGroup {
            width: min(620px, 100%) !important;
            margin: 0 auto 1.7rem auto !important;
        }

        .stButtonGroup > div {
            display: flex !important;
            width: 100% !important;
            gap: 0 !important;
            padding: 4px !important;
            background: #ffffff !important;
            border: 1px solid var(--joey-border) !important;
            border-radius: 999px !important;
            box-shadow: 0 10px 24px rgba(20, 55, 43, 0.10) !important;
            overflow: hidden !important;
        }

        .stButtonGroup button {
            flex: 1 1 50% !important;
            justify-content: center !important;
            min-height: 52px !important;
            padding: 0.7rem 1rem !important;
            border: 0 !important;
            border-radius: 999px !important;
            background: #ffffff !important;
            color: var(--joey-text) !important;
            font-size: 1rem !important;
            font-weight: 650 !important;
            box-shadow: none !important;
            transition:
                background-color 0.18s ease,
                color 0.18s ease !important;
        }

        .stButtonGroup button:hover {
            background: #f2f7f4 !important;
            color: var(--joey-green) !important;
        }

        .stButtonGroup button[aria-pressed="true"],
        .stButtonGroup button[aria-checked="true"],
        .stButtonGroup button[data-selected="true"] {
            background: var(--joey-green) !important;
            color: #ffffff !important;
        }

        .stButtonGroup button[aria-pressed="true"] *,
        .stButtonGroup button[aria-checked="true"] *,
        .stButtonGroup button[data-selected="true"] * {
            color: #ffffff !important;
        }

        .stButtonGroup button:focus-visible {
            outline: 3px solid rgba(18, 107, 87, 0.22) !important;
            outline-offset: 2px !important;
        }

        /* ---------------------------------------------------------
           Hey Joey speech bubble
        --------------------------------------------------------- */

        .joey-bubble-row {
            display: flex;
            align-items: flex-start;
            gap: 0.95rem;
            width: 100%;
            margin: 0.9rem 0 1rem 0;
        }

        .joey-bubble-avatar {
            flex: 0 0 62px;
            width: 62px;
            height: 62px;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 5px 14px rgba(20, 55, 43, 0.10);
            background: var(--joey-green);
        }

        .joey-bubble-avatar img {
            width: 100%;
            height: 100%;
            display: block;
            object-fit: cover;
        }

        .joey-bubble {
            position: relative;
            flex: 1 1 auto;
            min-width: 0;
            background: var(--joey-green-soft);
            border: 1px solid var(--joey-border);
            border-radius: 24px;
            padding: 1.15rem 1.3rem;
            color: #23313f;
            font-size: 1.02rem;
            line-height: 1.65;
            box-shadow: 0 7px 20px rgba(20, 55, 43, 0.05);
        }

        .joey-bubble::before {
            content: "";
            position: absolute;
            left: -11px;
            top: 21px;
            width: 20px;
            height: 20px;
            background: var(--joey-green-soft);
            border-left: 1px solid var(--joey-border);
            border-bottom: 1px solid var(--joey-border);
            transform: rotate(45deg);
        }

        .joey-bubble strong {
            color: var(--joey-green-dark);
        }

        .joey-bubble p:first-child {
            margin-top: 0;
        }

        .joey-bubble p:last-child {
            margin-bottom: 0;
        }

        .joey-strategy {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #dce8e0;
        }

        .joey-source {
            color: var(--joey-muted);
            font-size: 0.88rem;
            margin-top: 0.4rem;
        }

        /* ---------------------------------------------------------
           Input and send button
        --------------------------------------------------------- */

        div[data-testid="stForm"] {
            border: 1px solid var(--joey-border);
            border-radius: 18px;
            padding: 1rem;
            background: #ffffff;
        }

        div[data-baseweb="textarea"] textarea {
            border-radius: 14px;
            min-height: 130px;
            background: var(--joey-input);
            border-color: transparent;
        }

        div[data-baseweb="textarea"] textarea:focus {
            border-color: var(--joey-green) !important;
            box-shadow: 0 0 0 1px var(--joey-green) !important;
        }

        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            width: 100%;
            border-radius: 14px;
            min-height: 2.95rem;
            background: var(--joey-green);
            color: #ffffff;
            border: 1px solid var(--joey-green);
            font-weight: 700;
        }

        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: var(--joey-green-dark);
            border-color: var(--joey-green-dark);
            color: #ffffff;
        }

        @media (max-width: 650px) {
            .block-container {
                padding-top: 1.4rem;
            }

            .joey-header {
                gap: 12px;
            }

            .joey-header img {
                width: 76px;
                height: 76px;
            }

            .joey-header h1 {
                font-size: 2.25rem;
            }

            .joey-bubble-avatar {
                flex-basis: 50px;
                width: 50px;
                height: 50px;
                border-radius: 15px;
            }

            .joey-bubble {
                padding: 1rem;
                font-size: 0.96rem;
            }

            .joey-bubble::before {
                top: 16px;
            }
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
        "workflow_mode": "Record what happened",
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

    LOCAL_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_item = {
        "saved_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "source": "streamlit_speech_bubble_interface",
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
            session.current_record.model_dump(
                mode="json"
            )
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


def clean_text(
    value: str | None,
) -> str:
    """Normalise user-facing text."""

    return " ".join(
        (value or "").split()
    ).strip()


def safe_text(
    value: str | None,
) -> str:
    """Normalise and escape dynamic text for HTML rendering."""

    return html.escape(
        clean_text(value)
    )


def readable_list(
    values: list[str],
) -> str:
    """Join values into readable parent-facing prose."""

    clean_values = [
        safe_text(value)
        for value in values
    ]
    clean_values = [
        value
        for value in clean_values
        if value
    ]

    if not clean_values:
        return ""

    if len(clean_values) == 1:
        return clean_values[0]

    if len(clean_values) == 2:
        return (
            f"{clean_values[0]} "
            f"and {clean_values[1]}"
        )

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
            "anxiety was recorded as "
            f"{safe_text(record.anxiety_level.value.lower())}"
        )

    if record.mood_zone.value != "Unknown":
        details.append(
            "the mood zone was recorded as "
            f"{safe_text(record.mood_zone.value)}"
        )

    if record.environment:
        details.append(
            "the setting was "
            f"{safe_text(record.environment)}"
        )

    if record.possible_triggers:
        details.append(
            "possible triggers included "
            + readable_list(
                record.possible_triggers
            )
        )

    if details:
        return (
            "I have updated the same journal draft: "
            + "; ".join(details)
            + "."
        )

    return (
        "I have started a journal draft from what you described."
    )
def build_ready_for_review_response(
    session: JoeyConversationSession,
) -> str:
    """Build the final review prompt before saving."""

    record = session.current_record
    parts = [
        build_record_summary(session),
    ]

    if record.summary:
        parts.append(
            "My summary is: "
            f"{safe_text(record.summary)}"
        )

    if record.risk_flags:
        parts.append(
            "I also noticed information that may need "
            "safety-aware review."
        )

    parts.append(
        "Reply <strong>yes</strong> to confirm and save it, "
        "or <strong>no</strong> to discard it."
    )

    return " ".join(parts)


def handle_record_input(
    user_text: str,
) -> str:
    """Run the multi-turn journal workflow behind one text box."""

    command = clean_text(user_text)
    session: JoeyConversationSession | None = (
        st.session_state.record_session
    )

    if command.lower() in {
        "start over",
        "restart",
        "reset",
    }:
        st.session_state.record_session = None
        return (
            "Started over. Tell me what happened in your own words."
        )

    if session is None:
        session = JoeyConversationSession.start(
            command
        )
        st.session_state.record_session = session

        response = build_record_summary(
            session
        )

        if should_limit_strategy_suggestions(
            session.current_record
        ):
            response += (
                " I noticed a possible safety concern. "
                "Please make sure the child is safe and seek "
                "appropriate urgent or professional support "
                "when needed."
            )

        if (
            session.status
            == ConversationStatus.collecting_information
        ):
            response += (
                " "
                + safe_text(
                    session.follow_up_question
                )
            )
        else:
            response += (
                " "
                + build_ready_for_review_response(
                    session
                )
            )

        return response

    if (
        session.status
        == ConversationStatus.collecting_information
    ):
        session.submit_answer(command)
        st.session_state.record_session = session

        if (
            session.status
            == ConversationStatus.collecting_information
        ):
            return (
                build_record_summary(session)
                + " "
                + safe_text(
                    session.follow_up_question
                )
            )

        return build_ready_for_review_response(
            session
        )

    if (
        session.status
        == ConversationStatus.ready_for_review
    ):
        answer = command.lower()

        if answer in {
            "yes",
            "y",
            "confirm",
            "save",
        }:
            session.confirm()
            save_confirmed_session(session)
            st.session_state.record_session = None

            return (
                "The journal entry has been confirmed and recorded. "
                "Its structured fields are now available in the "
                "background for the Journal Entries and Insights "
                "integration layer. You can describe another event "
                "whenever you are ready."
            )

        if answer in {
            "no",
            "n",
            "discard",
            "reject",
        }:
            session.reject()
            st.session_state.record_session = None

            return (
                "The draft was discarded and nothing was saved. "
                "You can describe another event whenever you are ready."
            )

        return (
            "Please reply <strong>yes</strong> to confirm and save "
            "the draft, or <strong>no</strong> to discard it."
        )

    st.session_state.record_session = None

    return (
        "Tell me what happened and I will start a new journal draft."
    )


def clean_strategy_title(
    title: str | None,
) -> str:
    """Remove trailing age information from summary prose."""

    title = clean_text(title)

    return re.sub(
        r"\s*\(Ages?[^)]*\)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()


def build_strategy_response(
    question: str,
) -> str:
    """Return a readable answer and source-backed strategies."""

    screening_record = extract_structured_record(
        question
    )

    if should_limit_strategy_suggestions(
        screening_record
    ):
        return (
            "What you described may involve an immediate safety "
            "or injury concern. I will not provide ordinary strategy "
            "suggestions for that situation. Please make sure the "
            "child is safe and seek appropriate urgent or "
            "professional support."
        )

    service = get_strategy_service()
    result = service.retrieve(
        question=question,
        top_k=3,
        candidate_pool=6,
    )

    if not result.evidence:
        return (
            "I could not find a sufficiently relevant strategy "
            "in the current approved local collection."
        )

    titles = [
        clean_strategy_title(
            item.strategy_title
        )
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
            "helped somewhat"
            in item.history_note.lower()
            or "worked well"
            in item.history_note.lower()
        )
        for item in result.evidence
    ):
        response_parts.append(
            "Previous confirmed feedback also indicates that at "
            "least one related approach was reported to help."
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

        passage = clean_text(
            item.passage
        )

        passage_preview = (
            passage
            if len(passage) <= 360
            else (
                passage[:360]
                .rsplit(" ", maxsplit=1)[0]
                + "..."
            )
        )

        history_sentence = ""

        if (
            "new strategy option"
            not in item.history_note.lower()
        ):
            history_sentence = (
                "<br><em>"
                f"{html.escape(item.history_note)}"
                "</em>"
            )

        strategy_html.append(
            '<div class="joey-strategy">'
            f"<strong>{index}. {html.escape(title)}</strong><br>"
            f"{html.escape(passage_preview)}"
            f"{history_sentence}"
            '<div class="joey-source">'
            "Source: "
            f"{html.escape(item.collection_title)}"
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


def render_joey_bubble(
    message: str,
) -> None:
    """Render Joey's response inside a branded speech bubble."""

    st.markdown(
        f"""
        <div class="joey-bubble-row">
            <div class="joey-bubble-avatar">
                <img
                    src="{logo_data_uri()}"
                    alt="Hey Joey"
                >
            </div>
            <div class="joey-bubble">
                <strong>Joey</strong><br>
                {message}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Run the minimal Hey Joey Streamlit interface."""

    initialise_state()

    st.markdown(
        f"""
        <div class="joey-header">
            <img
                src="{logo_data_uri()}"
                alt="Hey Joey logo"
            >
            <h1>Hey Joey</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <p class="joey-subtitle">
            An AI prototype for the Hey Joey app.
        </p>
        """,
        unsafe_allow_html=True,
    )

    if not hasattr(
        st,
        "segmented_control",
    ):
        st.error(
            "This interface needs a newer Streamlit version. "
            "Run: python -m pip install --upgrade streamlit"
        )
        st.stop()

    selector_left, selector_column, selector_right = (
        st.columns(
            [0.45, 5.1, 0.45]
        )
    )

    with selector_column:
        mode = st.segmented_control(
            "Choose a workflow",
            options=[
                "Record what happened",
                "Ask for a strategy",
            ],
            default=st.session_state.get(
                "workflow_mode",
                "Record what happened",
            ),
            selection_mode="single",
            key="workflow_mode",
            label_visibility="collapsed",
            width="stretch",
        )

    if mode is None:
        mode = "Record what happened"

    if mode != st.session_state.last_mode:
        st.session_state.last_mode = mode

    current_response = (
        st.session_state.record_response
        if mode == "Record what happened"
        else st.session_state.strategy_response
    )

    render_joey_bubble(
        current_response
    )

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
            st.warning(
                "Please type a message."
            )
            return

        try:
            if mode == "Record what happened":
                st.session_state.record_response = (
                    handle_record_input(
                        clean_input
                    )
                )
            else:
                with st.spinner(
                    "Searching the approved local strategy library..."
                ):
                    st.session_state.strategy_response = (
                        build_strategy_response(
                            clean_input
                        )
                    )

            st.rerun()

        except (
            ValueError,
            RuntimeError,
        ) as error:
            if mode == "Record what happened":
                st.session_state.record_response = (
                    "I could not use that answer yet: "
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