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
           Scrollable chat history
        --------------------------------------------------------- */

        /*
        One continuous chat shell: scrollable messages above,
        composer attached directly underneath.
        */
        .st-key-chat_shell {
            width: 100%;
            overflow: visible;
            background: transparent;
            border: none;
            border-radius: 0;
            box-shadow: none;
        }

        .st-key-chat_shell > div,
        .st-key-chat_shell > div > div[data-testid="stVerticalBlock"],
        .st-key-chat_shell div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }

        .st-key-chat_history {
            height: 500px;
            overflow-y: auto;
            padding: 0.6rem 0.4rem 1rem 0.4rem;
            margin: 0 !important;
            background: transparent;
            border: none !important;
            border-radius: 0 !important;
            scroll-behavior: smooth;
        }

        .st-key-chat_history::-webkit-scrollbar {
            width: 9px;
        }

        .st-key-chat_history::-webkit-scrollbar-track {
            background: transparent;
        }

        .st-key-chat_history::-webkit-scrollbar-thumb {
            background: #c9d7d0;
            border-radius: 999px;
        }

        .chat-row {
            display: flex;
            width: 100%;
            margin: 0.7rem 0;
        }

        .chat-row.assistant {
            justify-content: flex-start;
            align-items: flex-start;
            gap: 0.75rem;
        }

        .chat-row.user {
            justify-content: flex-end;
        }

        .chat-avatar {
            flex: 0 0 48px;
            width: 48px;
            height: 48px;
            border-radius: 15px;
            overflow: hidden;
            background: var(--joey-green);
            box-shadow: 0 4px 12px rgba(20, 55, 43, 0.12);
        }

        .chat-avatar img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }

        .chat-bubble {
            position: relative;
            max-width: 78%;
            padding: 0.9rem 1.05rem;
            border-radius: 20px;
            font-size: 1rem;
            line-height: 1.58;
            overflow-wrap: anywhere;
        }

        .chat-bubble.assistant {
            background: var(--joey-green);
            color: #ffffff;
            border-top-left-radius: 7px;
            box-shadow: 0 6px 16px rgba(18, 107, 87, 0.16);
        }

        .chat-bubble.assistant::before {
            content: "";
            position: absolute;
            left: -8px;
            top: 15px;
            width: 16px;
            height: 16px;
            background: var(--joey-green);
            transform: rotate(45deg);
        }

        .chat-bubble.user {
            background: #ffffff;
            color: var(--joey-text);
            border: 1px solid var(--joey-border);
            border-top-right-radius: 7px;
            box-shadow: 0 5px 14px rgba(20, 55, 43, 0.06);
        }

        .chat-bubble.user::after {
            content: "";
            position: absolute;
            right: -8px;
            top: 15px;
            width: 16px;
            height: 16px;
            background: #ffffff;
            border-top: 1px solid var(--joey-border);
            border-right: 1px solid var(--joey-border);
            transform: rotate(45deg);
        }

        .chat-name {
            display: block;
            margin-bottom: 0.25rem;
            font-size: 0.82rem;
            font-weight: 750;
        }

        .chat-bubble.assistant .chat-name {
            color: #ffffff;
        }

        .chat-bubble.user .chat-name {
            color: var(--joey-green-dark);
            text-align: right;
        }

        .chat-bubble.assistant strong,
        .chat-bubble.assistant em,
        .chat-bubble.assistant p,
        .chat-bubble.assistant div {
            color: #ffffff;
        }

        .chat-bubble.assistant p:first-child {
            margin-top: 0;
        }

        .chat-bubble.assistant p:last-child {
            margin-bottom: 0;
        }

        .joey-strategy {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(255, 255, 255, 0.30);
        }

        .joey-source {
            color: rgba(255, 255, 255, 0.82) !important;
            font-size: 0.88rem;
            margin-top: 0.4rem;
        }

        /* ---------------------------------------------------------
           Input and send button
        --------------------------------------------------------- */

        /*
        The form is attached to the bottom of the chat shell rather
        than appearing as a separate card.
        */
        .st-key-chat_shell div[data-testid="stForm"] {
            width: 100% !important;
            max-width: none !important;
            margin: 0 !important;
            padding: 0.75rem 0.4rem 0 0.4rem !important;
            background: transparent;
            border: none !important;
            border-radius: 0 !important;
        }

        div[data-baseweb="textarea"] textarea {
            border-radius: 22px;
            min-height: 110px;
            background: var(--joey-input);
            border: 1px solid var(--joey-border);
            padding: 1rem;
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

            .st-key-chat_shell {
                border-radius: 18px;
            }

            .st-key-chat_history {
                height: 430px;
                padding: 0.4rem 0.45rem 0.8rem 0.45rem;
            }

            .st-key-chat_shell div[data-testid="stForm"] {
                width: 100% !important;
                padding: 0.75rem 0 0 0 !important;
            }

            .chat-avatar {
                flex-basis: 40px;
                width: 40px;
                height: 40px;
                border-radius: 13px;
            }

            .chat-bubble {
                max-width: 82%;
                padding: 0.8rem 0.9rem;
                font-size: 0.95rem;
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
    """Create separate persistent chat histories for both workflows."""

    record_greeting = (
        "Tell me what happened in your own words. "
        "I will turn it into a journal draft and ask only "
        "for details that are still needed."
    )

    strategy_greeting = (
        "Ask what support strategy may be relevant. "
        "I will search the approved local Hey Joey strategy library."
    )

    defaults: dict[str, Any] = {
        "record_session": None,
        "last_mode": "Record what happened",
        "workflow_mode": "Record what happened",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Migrate older response-only state when the app hot-reloads.
    if "record_chat_history" not in st.session_state:
        old_record = st.session_state.get(
            "record_response",
            [record_greeting],
        )

        if isinstance(old_record, str):
            old_record = [old_record]

        st.session_state.record_chat_history = [
            {
                "role": "assistant",
                "content": message,
            }
            for message in old_record
        ]

    if "strategy_chat_history" not in st.session_state:
        old_strategy = st.session_state.get(
            "strategy_response",
            [strategy_greeting],
        )

        if isinstance(old_strategy, str):
            old_strategy = [old_strategy]

        st.session_state.strategy_chat_history = [
            {
                "role": "assistant",
                "content": message,
            }
            for message in old_strategy
        ]


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


def build_initial_record_summary(
    session: JoeyConversationSession,
) -> str:
    """
    Summarise only the information extracted from the initial note.

    This appears once after the first observation and is not repeated
    after later follow-up answers.
    """

    record = session.current_record
    details: list[str] = []

    if record.anxiety_level.value != "Unknown":
        details.append(
            "anxiety was initially understood as "
            f"{safe_text(record.anxiety_level.value.lower())}"
        )

    if record.mood_zone.value != "Unknown":
        details.append(
            "the mood zone was initially understood as "
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

    if not details:
        return (
            "I have created a journal draft from what you described."
        )

    return (
        "I have created a journal draft: "
        + "; ".join(details)
        + "."
    )


def build_answer_acknowledgement(
    field_name: str | None,
    answer: str,
    session: JoeyConversationSession,
) -> str:
    """
    Acknowledge only the latest answer.

    Previously collected information is deliberately not repeated.
    """

    clean_answer = clean_text(answer)
    record = session.current_record

    skipped_answers = {
        "i don't know",
        "i do not know",
        "don't know",
        "do not know",
        "not sure",
        "unsure",
        "skip",
        "unknown",
    }

    if clean_answer.lower() in skipped_answers:
        return (
            "I have left that detail as unknown in the journal draft."
        )

    if field_name == "possible_triggers":
        return (
            "I have added this possible trigger to the draft: "
            f"{safe_text(clean_answer)}"
        )

    if field_name == "anxiety_level":
        return (
            "I have recorded the anxiety level as "
            f"{safe_text(record.anxiety_level.value)}."
        )

    if field_name == "mood":
        mood_text = safe_text(
            record.mood_zone.value
        )

        if record.mood_labels:
            mood_text += (
                ", with "
                + readable_list(
                    record.mood_labels
                )
            )

        return (
            "I have updated the mood information to "
            f"{mood_text}."
        )

    if field_name == "environment":
        return (
            "I have recorded the setting as "
            f"{safe_text(record.environment)}."
        )

    if field_name == "safety_status":
        return (
            "I have added the safety information you provided "
            "to the draft."
        )

    if field_name == "medication_context":
        return (
            "I have added the medication context to the draft. "
            "Joey does not provide medication or dosage advice."
        )

    return (
        "I have added that detail to the same journal draft."
    )


def build_final_summary(
    session: JoeyConversationSession,
) -> str:
    """Create the final summary as its own speech bubble."""

    record = session.current_record

    if record.summary:
        return (
            "My summary is: "
            f"{safe_text(record.summary)}"
        )

    return (
        "The journal draft is now ready for your review."
    )


def build_confirmation_prompt() -> str:
    """Create the confirmation request as its own speech bubble."""

    return (
        "Reply <strong>yes</strong> to confirm and save the "
        "journal entry, or <strong>no</strong> to discard it."
    )


def handle_record_input(
    user_text: str,
) -> list[str]:
    """
    Run the multi-turn journal workflow.

    Each returned list item is rendered as a separate Joey bubble.
    """

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

        return [
            (
                "Started over. Tell me what happened "
                "in your own words."
            )
        ]

    # First parent observation.
    if session is None:
        session = JoeyConversationSession.start(
            command
        )

        st.session_state.record_session = session

        messages: list[str] = [
            build_initial_record_summary(
                session
            )
        ]

        if should_limit_strategy_suggestions(
            session.current_record
        ):
            messages.append(
                (
                    "I noticed a possible safety concern. "
                    "Please make sure the child is safe and seek "
                    "appropriate urgent or professional support "
                    "when needed."
                )
            )

        if (
            session.status
            == ConversationStatus.collecting_information
        ):
            # The follow-up question has its own bubble.
            messages.append(
                safe_text(
                    session.follow_up_question
                )
            )
        else:
            messages.extend(
                [
                    build_final_summary(
                        session
                    ),
                    build_confirmation_prompt(),
                ]
            )

        return messages

    # Parent answers a follow-up question.
    if (
        session.status
        == ConversationStatus.collecting_information
    ):
        # Capture the field before the session advances to the next one.
        answered_field = session.pending_field

        session.submit_answer(
            command
        )

        st.session_state.record_session = session

        messages = [
            build_answer_acknowledgement(
                field_name=answered_field,
                answer=command,
                session=session,
            )
        ]

        if (
            session.status
            == ConversationStatus.collecting_information
        ):
            # The next follow-up question has its own bubble.
            messages.append(
                safe_text(
                    session.follow_up_question
                )
            )
        else:
            # Summary and confirmation each have their own bubble.
            messages.extend(
                [
                    build_final_summary(
                        session
                    ),
                    build_confirmation_prompt(),
                ]
            )

        return messages

    # Parent confirms or rejects the completed draft.
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

            save_confirmed_session(
                session
            )

            st.session_state.record_session = None

            return [
                (
                    "The journal entry has been confirmed and recorded."
                ),
                (
                    "Its structured information is now available "
                    "in the background for the Journal Entries and "
                    "Insights integration layer."
                ),
            ]

        if answer in {
            "no",
            "n",
            "discard",
            "reject",
        }:
            session.reject()
            st.session_state.record_session = None

            return [
                (
                    "The draft was discarded and nothing was saved."
                )
            ]

        return [
            (
                "Please reply <strong>yes</strong> to confirm and "
                "save the draft, or <strong>no</strong> to discard it."
            )
        ]

    st.session_state.record_session = None

    return [
        (
            "Tell me what happened and I will start "
            "a new journal draft."
        )
    ]


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


def render_chat_message(
    role: str,
    content: str,
) -> None:
    """Render one Joey or sender message as a chat bubble."""

    if role == "user":
        safe_content = html.escape(
            content
        ).replace(
            "\n",
            "<br>",
        )

        message_html = (
            '<div class="chat-row user">'
            '<div class="chat-bubble user">'
            '<span class="chat-name">You</span>'
            f'{safe_content}'
            '</div>'
            '</div>'
        )

    else:
        # Assistant content is generated internally. Dynamic values
        # inside it are escaped by the response-building functions.
        message_html = (
            '<div class="chat-row assistant">'
            '<div class="chat-avatar">'
            f'<img src="{logo_data_uri()}" alt="Joey">'
            '</div>'
            '<div class="chat-bubble assistant">'
            '<span class="chat-name">Joey</span>'
            f'{content}'
            '</div>'
            '</div>'
        )

    if hasattr(st, "html"):
        st.html(message_html)
    else:
        st.markdown(
            message_html,
            unsafe_allow_html=True,
        )


def render_chat_history(
    history: list[dict[str, str]],
) -> None:
    """Render the selected workflow's scrollable message history."""

    with st.container(
        height=500,
        border=False,
        key="chat_history",
    ):
        for message in history:
            render_chat_message(
                role=message["role"],
                content=message["content"],
            )


def main() -> None:
    """Run the Hey Joey chat-style Streamlit interface."""

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
            An AI chatbot prototype for the Hey Joey app.
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

    history_key = (
        "record_chat_history"
        if mode == "Record what happened"
        else "strategy_chat_history"
    )

    history: list[dict[str, str]] = (
        st.session_state[history_key]
    )

    with st.container(
        key="chat_shell",
    ):
        render_chat_history(
            history
        )

        with st.form(
            f"chat_input_form_{mode}",
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

        # Keep the sender's message in the visible conversation.
        history.append(
            {
                "role": "user",
                "content": clean_input,
            }
        )

        try:
            if mode == "Record what happened":
                assistant_messages = handle_record_input(
                    clean_input
                )
            else:
                with st.spinner(
                    "Searching the approved local strategy library..."
                ):
                    assistant_messages = [
                        build_strategy_response(
                            clean_input
                        )
                    ]

            for message in assistant_messages:
                history.append(
                    {
                        "role": "assistant",
                        "content": message,
                    }
                )

        except (
            ValueError,
            RuntimeError,
        ) as error:
            if mode == "Record what happened":
                error_message = (
                    "I could not use that answer yet: "
                    f"{html.escape(str(error))}"
                )
            else:
                error_message = (
                    "I could not complete the strategy search: "
                    f"{html.escape(str(error))}"
                )

            history.append(
                {
                    "role": "assistant",
                    "content": error_message,
                }
            )

        st.session_state[history_key] = history
        st.rerun()


if __name__ == "__main__":
    main()