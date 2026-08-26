from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import streamlit as st

from app.api_client import (
    HeyJoeyApiClient,
    HeyJoeyApiError,
    InvalidApiResponseError,
)
from app.settings import get_settings
from app.streamlit_api_adapter import (
    RECORD_GREETING,
    RESET_GREETING,
    STRATEGY_GREETING,
    build_strategy_feedback_prompt,
    build_strategy_response_html,
    conversation_history_from_response,
    parse_strategy_feedback,
    record_history_from_response,
    restore_record_frontend_state,
    restore_strategy_frontend_state,
)


# Resolve the logo path relative to the repository so the interface does
# not depend on the process working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = PROJECT_ROOT / "assets" / "hey_joey_logo.png"


def logo_data_uri() -> str:
    """Return the local logo as an embeddable data URI."""

    # Encode the local image as a data URI so it can be embedded directly
    # inside the custom chat/header HTML.
    encoded = base64.b64encode(
        LOGO_PATH.read_bytes()
    ).decode("ascii")

    return f"data:image/png;base64,{encoded}"


# Configure the Streamlit page before rendering any visible components.
st.set_page_config(
    page_title="Hey Joey",
    page_icon=str(LOGO_PATH),
    layout="centered",
    initial_sidebar_state="collapsed",
)


# Apply the custom Hey Joey presentation layer. The CSS changes appearance
# only; workflow logic remains in the Python functions below.
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



# Cache one HTTP client so reruns reuse the same local connection pool
# instead of constructing a new client for every Streamlit interaction.
@st.cache_resource(show_spinner=False)
def get_api_client() -> HeyJoeyApiClient:
    """Create one reusable local FastAPI client."""

    return HeyJoeyApiClient()


def initialise_state() -> None:
    """Restore both workflow histories through the FastAPI backend."""

    # Provide safe initial values so the UI can render even before stored
    # workflow state has been restored from FastAPI.
    defaults: dict[str, Any] = {
        "last_mode": "Record what happened",
        "workflow_mode": "Record what happened",
        "frontend_state_loaded": False,
        "backend_error": None,
        "record_chat_history": [
            {
                "role": "assistant",
                "content": html.escape(
                    RECORD_GREETING
                ),
            }
        ],
        "strategy_chat_history": [
            {
                "role": "assistant",
                "content": html.escape(
                    STRATEGY_GREETING
                ),
            }
        ],
        "record_session_id": None,
        "record_status": "active",
        "strategy_conversation_id": None,
        "pending_strategy_feedback": None,
    }

    # Initialise only missing keys so Streamlit reruns do not overwrite
    # the current conversation state.
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Restore backend state only once per frontend session unless a retry
    # explicitly clears this flag.
    if st.session_state.frontend_state_loaded:
        return

    client = get_api_client()

    try:
        # Verify the FastAPI service is healthy before attempting to restore
        # either workflow history.
        health = client.health()

        if health.get(
            "status"
        ) != "ok":
            raise InvalidApiResponseError(
                "The FastAPI health response was not healthy."
            )

        # Restore journal and strategy workflows independently from their
        # persisted API state.
        record_state = (
            restore_record_frontend_state(
                client
            )
        )
        strategy_state = (
            restore_strategy_frontend_state(
                client
            )
        )
    # Preserve the attempted user message and show a safe error bubble if the
    # backend request fails, rather than losing the interaction on rerun.
    except HeyJoeyApiError as error:
        st.session_state.backend_error = str(
            error
        )
        st.session_state.frontend_state_loaded = True
        return

    st.session_state.record_chat_history = (
        record_state.history
    )
    st.session_state.record_session_id = (
        record_state.conversation_id
    )
    st.session_state.record_status = (
        record_state.status
    )

    st.session_state.strategy_chat_history = (
        strategy_state.history
    )
    st.session_state.strategy_conversation_id = (
        strategy_state.conversation_id
    )

    # Restore the pending feedback target so ratings can continue after a
    # Streamlit rerun or browser refresh.
    pending = strategy_state.metadata.get(
        "pending_strategy_feedback"
    )
    st.session_state.pending_strategy_feedback = (
        pending
        if isinstance(
            pending,
            dict,
        )
        else None
    )

    st.session_state.backend_error = None
    st.session_state.frontend_state_loaded = True


def clean_text(
    value: str | None,
) -> str:
    """Normalise user-facing text."""

    return " ".join(
        (value or "").split()
    ).strip()


def render_chat_message(
    role: str,
    content: str,
) -> None:
    """Render one Joey or sender message as a chat bubble."""

    # Escape user text before inserting it into custom HTML chat bubbles.
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
        # Assistant HTML is generated by trusted frontend adapters and may
        # therefore contain the strategy cards built by the adapter layer.
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

    # Prefer Streamlit's HTML renderer when available, with markdown as a
    # compatibility fallback for older versions.
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

    # Keep message history in a fixed-height scrollable container above the
    # attached composer.
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


def _record_confirmation_prompt() -> str:
    return (
        "Please reply <strong>yes</strong> to confirm and save "
        "the draft, or <strong>no</strong> to discard it."
    )


def _set_record_response(
    response: dict[str, Any],
) -> None:
    """Update the record workflow from the API source of truth."""

    # Treat the API response as the source of truth after every record
    # workflow mutation.
    st.session_state.record_session_id = int(
        response["session_id"]
    )
    st.session_state.record_status = str(
        response.get(
            "status",
            "active",
        )
    )
    st.session_state.record_chat_history = (
        record_history_from_response(
            response
        )
    )


def process_record_input(
    client: HeyJoeyApiClient,
    user_text: str,
) -> None:
    """Send one journal workflow action through FastAPI."""

    # Normalise the message once before interpreting commands or forwarding
    # it to the backend.
    command = clean_text(
        user_text
    )
    lowered = command.lower()

    # A reset creates a fresh generic placeholder and clears the active
    # record-workflow session ID without deleting previous stored history.
    if lowered in {
        "start over",
        "restart",
        "reset",
    }:
        response = client.create_conversation(
            workflow="record_observation",
            greeting=RESET_GREETING,
        )
        st.session_state.record_chat_history = (
            conversation_history_from_response(
                response,
                workflow="record_observation",
            )
        )
        st.session_state.record_session_id = None
        st.session_state.record_status = "active"
        return

    session_id = st.session_state.get(
        "record_session_id"
    )
    current_status = str(
        st.session_state.get(
            "record_status",
            "active",
        )
    )

    # Start a new record workflow when no draft exists or the previous one
    # has already reached a terminal state.
    if (
        session_id is None
        or current_status
        in {
            "confirmed",
            "rejected",
            "completed",
            "archived",
        }
    ):
        response = client.create_record_session(
            command
        )
        _set_record_response(
            response
        )
        return

    numeric_session_id = int(
        session_id
    )

    # Active record sessions accept ordinary follow-up answers.
    if current_status == "active":
        response = client.submit_record_message(
            numeric_session_id,
            command,
        )
        _set_record_response(
            response
        )
        return

    # Once review-ready, only explicit yes/no-style commands can confirm or
    # reject the draft; other input receives the confirmation prompt again.
    if current_status == "ready_for_review":
        if lowered in {
            "yes",
            "y",
            "confirm",
            "save",
        }:
            response = client.confirm_record_session(
                numeric_session_id
            )
            _set_record_response(
                response
            )
            return

        if lowered in {
            "no",
            "n",
            "discard",
            "reject",
        }:
            response = client.reject_record_session(
                numeric_session_id
            )
            _set_record_response(
                response
            )
            return

        response = client.append_conversation_exchange(
            session_id=numeric_session_id,
            user_content=command,
            user_message_type="confirmation_response",
            assistant_messages=[
                _record_confirmation_prompt()
            ],
            assistant_message_type="confirmation_prompt",
        )
        st.session_state.record_chat_history = (
            conversation_history_from_response(
                response,
                workflow="record_observation",
            )
        )
        return

# If an unexpected status reaches this point, recover by starting a new
# API-backed draft rather than mutating an unknown workflow state.
    # A defensive fallback starts a fresh API-backed draft.
    response = client.create_record_session(
        command
    )
    _set_record_response(
        response
    )


def _ensure_strategy_conversation(
    client: HeyJoeyApiClient,
) -> int:
    session_id = st.session_state.get(
        "strategy_conversation_id"
    )

    # Reuse the persistent strategy conversation when it has already been
    # created for this frontend session.
    if session_id is not None:
        return int(
            session_id
        )

    # Create the strategy conversation lazily on the first strategy action.
    response = client.create_conversation(
        workflow="ask_strategy",
        greeting=STRATEGY_GREETING,
    )
    session_id = int(
        response["session_id"]
    )
    st.session_state.strategy_conversation_id = (
        session_id
    )
    st.session_state.strategy_chat_history = (
        conversation_history_from_response(
            response,
            workflow="ask_strategy",
        )
    )

    return session_id


def process_strategy_input(
    client: HeyJoeyApiClient,
    user_text: str,
) -> None:
    """Send one strategy search or rating through FastAPI."""

    command = clean_text(
        user_text
    )
    session_id = _ensure_strategy_conversation(
        client
    )
    # A single chat input supports either a new strategy query or a rating of
    # one of the strategies from the most recent accepted search.
    parsed_feedback = parse_strategy_feedback(
        command
    )
    pending = st.session_state.get(
        "pending_strategy_feedback"
    )

    # Feedback is handled only when the whole message matches the expected
    # rank-plus-rating format.
    if parsed_feedback is not None:
        strategy_rank, rating = parsed_feedback

        # Ratings require a stored pending search target; otherwise there is
        # no safe way to know which displayed strategy is being rated.
        if not isinstance(
            pending,
            dict,
        ):
            assistant_messages = [
                (
                    "There is no recent strategy search available for "
                    "feedback. Ask for a strategy first."
                )
            ]
        else:
            search_id = int(
                pending["search_id"]
            )
            strategy_count = int(
                pending["strategy_count"]
            )

            # Reject ranks outside the set that was actually displayed to the
            # parent/carer.
            if strategy_rank > strategy_count:
                assistant_messages = [
                    (
                        f"That search displayed {strategy_count} "
                        f"{'strategy' if strategy_count == 1 else 'strategies'}. "
                        "Please use one of the displayed strategy numbers."
                    )
                ]
            else:
                # Submit feedback against the persisted search ID and the
                # displayed strategy rank from that search.
                feedback_response = (
                    client.submit_strategy_feedback(
                        search_id=search_id,
                        strategy_rank=strategy_rank,
                        rating=rating,
                    )
                )
                message = html.escape(
                    str(
                        feedback_response.get(
                            "message",
                            (
                                "The strategy feedback was recorded."
                            ),
                        )
                    )
                )
                assistant_messages = [
                    message,
                    (
                        "You can rate another strategy from the same "
                        "response or ask a new strategy question."
                    ),
                ]

        response = client.append_conversation_exchange(
            session_id=session_id,
            user_content=command,
            user_message_type="strategy_feedback",
            assistant_messages=assistant_messages,
            assistant_message_type=(
                "strategy_feedback_response"
            ),
            metadata={
                "pending_strategy_feedback": pending
            } if isinstance(
                pending,
                dict,
            ) else {},
        )
    else:
        # Non-feedback input is treated as a new strategy search.
        with st.spinner(
            "Searching the approved local strategy library. "
            "The first search may take longer while the local "
            "semantic model loads..."
        ):
            search_response = client.search_strategies(
                command,
                top_k=3,
            )

        assistant_messages = [
            build_strategy_response_html(
                search_response
            )
        ]

        # A new pending feedback target is created only when the backend says
        # the accepted search can be rated.
        next_pending: dict[str, int] | None = None

        if (
            bool(
                search_response.get(
                    "can_submit_feedback"
                )
            )
            and search_response.get(
                "search_id"
            ) is not None
        ):
            strategy_count = int(
                search_response.get(
                    "strategy_count",
                    0,
                )
            )
            next_pending = {
                "search_id": int(
                    search_response["search_id"]
                ),
                "strategy_count": strategy_count,
            }
            assistant_messages.append(
                build_strategy_feedback_prompt(
                    strategy_count
                )
            )

        # Replace any older pending target with the latest accepted search.
        st.session_state.pending_strategy_feedback = (
            next_pending
        )

        response = client.append_conversation_exchange(
            session_id=session_id,
            user_content=command,
            user_message_type="strategy_question",
            assistant_messages=assistant_messages,
            assistant_message_type="strategy_response",
            metadata={
                "pending_strategy_feedback": (
                    next_pending
                )
            } if next_pending is not None else {},
        )

    st.session_state.strategy_chat_history = (
        conversation_history_from_response(
            response,
            workflow="ask_strategy",
        )
    )


def main() -> None:
    """Run the Hey Joey Streamlit frontend over HTTP."""

    # Restore persisted workflow state before rendering controls or messages.
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

    # The frontend uses the same validated settings as the API, including
    # synthetic-only mode safeguards.
    settings = get_settings()

    # Warn users not to enter real family information while the prototype is
    # running under the synthetic-only data policy.
    if settings.synthetic_only:
        st.warning(
            "Synthetic demonstration mode is active. Do not enter "
            "real names, contact details, school details, medical "
            "identifiers or other private family information."
        )

    backend_error = st.session_state.get(
        "backend_error"
    )

    # Stop normal interaction when FastAPI is unavailable and offer an
    # explicit retry that forces state restoration on the next rerun.
    if backend_error:
        st.error(
            str(
                backend_error
            )
        )

        if st.button(
            "Retry backend connection",
            type="primary",
            width="stretch",
        ):
            st.session_state.frontend_state_loaded = False
            st.session_state.backend_error = None
            st.rerun()

        st.stop()

    # Fail clearly on older Streamlit versions that lack the workflow
    # selector used by this interface.
    if not hasattr(
        st,
        "segmented_control",
    ):
        st.error(
            "This interface needs a newer Streamlit version. "
            "Run: python -m pip install --upgrade streamlit"
        )
        st.stop()

    _, selector_column, _ = st.columns(
        [0.45, 5.1, 0.45]
    )

    with selector_column:
        mode = st.segmented_control(
            "Choose a workflow",
            options=[
                "Record what happened",
                "Ask for a strategy",
            ],
            selection_mode="single",
            key="workflow_mode",
            label_visibility="collapsed",
            width="stretch",
        )

    if mode is None:
        mode = "Record what happened"

    if mode != st.session_state.last_mode:
        st.session_state.last_mode = mode

    # Select the independent chat history associated with the active workflow.
    history_key = (
        "record_chat_history"
        if mode == "Record what happened"
        else "strategy_chat_history"
    )

    history: list[dict[str, str]] = (
        st.session_state[history_key]
    )

    # Render the current workflow history and its composer inside one shared
    # chat shell.
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

    # Streamlit reruns continuously; process input only after form submission.
    if not submitted:
        return

    clean_input = clean_text(
        str(user_text or "")
    )

    # Reject blank/whitespace-only messages before making an API request.
    if not clean_input:
        st.warning(
            "Please type a message."
        )
        return

    client = get_api_client()

    # Route the submitted message to the selected workflow while handling
    # controlled frontend API errors below.
    try:
        if mode == "Record what happened":
            process_record_input(
                client,
                clean_input,
            )
        else:
            process_strategy_input(
                client,
                clean_input,
            )
    except HeyJoeyApiError as error:
        current_history: list[
            dict[str, str]
        ] = list(
            st.session_state[
                history_key
            ]
        )
        current_history.extend(
            [
                {
                    "role": "user",
                    "content": clean_input,
                },
                {
                    "role": "assistant",
                    "content": (
                        "I could not complete the FastAPI request: "
                        f"{html.escape(str(error))}"
                    ),
                },
            ]
        )
        st.session_state[
            history_key
        ] = current_history

    # Rerun immediately so updated session-state history is rendered.
    st.rerun()


# Allow the module to be executed directly as the Streamlit application entry point.
if __name__ == "__main__":
    main()
