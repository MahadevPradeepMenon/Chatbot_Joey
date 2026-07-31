"""Framework-neutral helpers for the Streamlit HTTP frontend."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.api_client import (
    ApiResponseError,
    HeyJoeyApiClient,
)


RECORD_GREETING = (
    "Tell me what happened in your own words. "
    "I will turn it into a journal draft and ask only "
    "for details that are still needed."
)

STRATEGY_GREETING = (
    "Ask what support strategy may be relevant. "
    "I will search the approved local Hey Joey strategy library."
)

RESET_GREETING = (
    "Started over. Tell me what happened in your own words."
)

STRATEGY_FEEDBACK_PATTERN = re.compile(
    r"^\s*(\d+)\s*[-:.)]?\s*"
    r"(worked well|helped somewhat|not relevant|"
    r"did not work well)\s*$",
    flags=re.IGNORECASE,
)

FEEDBACK_API_VALUES = {
    "worked well": "worked_well",
    "helped somewhat": "helped_somewhat",
    "not relevant": "not_relevant",
    "did not work well": "did_not_work_well",
}


@dataclass(frozen=True)
class RestoredFrontendState:
    """One workflow state reconstructed through the HTTP API."""

    conversation_id: int | None
    status: str
    history: list[dict[str, str]]
    metadata: dict[str, Any]
    draft_state: dict[str, Any] | None


def clean_text(
    value: str | None,
) -> str:
    return " ".join(
        (value or "").split()
    ).strip()


def _message_content(
    message: Mapping[str, Any],
    *,
    assistant_html: bool,
) -> str:
    """Return safe display content for one API message."""

    content = str(
        message.get(
            "content",
            "",
        )
    )
    role = str(
        message.get(
            "role",
            "",
        )
    )
    message_type = str(
        message.get(
            "message_type",
            "",
        )
    )

    if role == "user":
        if (
            message_type
            == "confirmation_command"
        ):
            if content.lower() == "confirm":
                return "yes"
            if content.lower() == "reject":
                return "no"

        return content

    if assistant_html:
        return content

    if (
        message_type
        == "confirmation_prompt"
    ):
        return (
            "Reply <strong>yes</strong> to confirm and save the "
            "journal entry, or <strong>no</strong> to discard it."
        )

    return html.escape(
        content
    ).replace(
        "\n",
        "<br>",
    )


def normalise_api_messages(
    messages: Sequence[Mapping[str, Any]],
    *,
    greeting: str,
    assistant_html: bool,
) -> list[dict[str, str]]:
    """Convert API messages into the existing chat-bubble structure."""

    history: list[dict[str, str]] = []

    for message in messages:
        role = str(
            message.get(
                "role",
                "",
            )
        ).strip().lower()

        if role not in {
            "user",
            "assistant",
        }:
            continue

        content = _message_content(
            message,
            assistant_html=assistant_html,
        )

        if not clean_text(
            content
        ):
            continue

        history.append(
            {
                "role": role,
                "content": content,
            }
        )

    if (
        not history
        or history[0].get("role") != "assistant"
        or clean_text(
            re.sub(
                r"<[^>]+>",
                " ",
                history[0].get(
                    "content",
                    "",
                ),
            )
        )
        != clean_text(greeting)
    ):
        history.insert(
            0,
            {
                "role": "assistant",
                "content": html.escape(
                    greeting
                ),
            },
        )

    return history


def _restore_or_create(
    client: HeyJoeyApiClient,
    *,
    workflow: str,
    greeting: str,
    assistant_html: bool,
) -> dict[str, Any]:
    """Load the latest workflow conversation or create a placeholder."""

    try:
        return client.get_latest_conversation(
            workflow
        )
    except ApiResponseError as error:
        if error.status_code != 404:
            raise

    return client.create_conversation(
        workflow=workflow,
        greeting=greeting,
    )


def restore_record_frontend_state(
    client: HeyJoeyApiClient,
) -> RestoredFrontendState:
    """Restore the latest journal conversation through FastAPI."""

    response = _restore_or_create(
        client,
        workflow="record_observation",
        greeting=RECORD_GREETING,
        assistant_html=False,
    )
    draft_state = response.get(
        "draft_state"
    )

    if not isinstance(
        draft_state,
        dict,
    ):
        draft_state = None

    status = str(
        response.get(
            "status",
            "active",
        )
    )
    response_id = int(
        response["session_id"]
    )

    # Placeholder conversations have no draft and must not be sent to
    # the record workflow endpoints.
    conversation_id = (
        response_id
        if draft_state is not None
        else None
    )

    return RestoredFrontendState(
        conversation_id=conversation_id,
        status=status,
        history=normalise_api_messages(
            response.get(
                "messages",
                [],
            ),
            greeting=RECORD_GREETING,
            assistant_html=False,
        ),
        metadata=dict(
            response.get(
                "metadata",
                {},
            )
            or {}
        ),
        draft_state=draft_state,
    )


def restore_strategy_frontend_state(
    client: HeyJoeyApiClient,
) -> RestoredFrontendState:
    """Restore the persistent strategy chat through FastAPI."""

    response = _restore_or_create(
        client,
        workflow="ask_strategy",
        greeting=STRATEGY_GREETING,
        assistant_html=True,
    )
    response_id = int(
        response["session_id"]
    )

    return RestoredFrontendState(
        conversation_id=response_id,
        status=str(
            response.get(
                "status",
                "active",
            )
        ),
        history=normalise_api_messages(
            response.get(
                "messages",
                [],
            ),
            greeting=STRATEGY_GREETING,
            assistant_html=True,
        ),
        metadata=dict(
            response.get(
                "metadata",
                {},
            )
            or {}
        ),
        draft_state=None,
    )


def record_history_from_response(
    response: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Build record chat history from a record-workflow API response."""

    return normalise_api_messages(
        response.get(
            "messages",
            [],
        ),
        greeting=RECORD_GREETING,
        assistant_html=False,
    )


def conversation_history_from_response(
    response: Mapping[str, Any],
    *,
    workflow: str,
) -> list[dict[str, str]]:
    """Build chat history from the generic conversation API."""

    is_strategy = (
        workflow == "ask_strategy"
    )

    return normalise_api_messages(
        response.get(
            "messages",
            [],
        ),
        greeting=(
            STRATEGY_GREETING
            if is_strategy
            else RECORD_GREETING
        ),
        assistant_html=is_strategy,
    )


def parse_strategy_feedback(
    value: str,
) -> tuple[int, str] | None:
    """Parse chat feedback and return the API rating value."""

    match = STRATEGY_FEEDBACK_PATTERN.fullmatch(
        clean_text(value)
    )

    if match is None:
        return None

    rank = int(
        match.group(1)
    )
    label = clean_text(
        match.group(2)
    ).lower()

    return rank, FEEDBACK_API_VALUES[label]


def feedback_display_label(
    rating: str,
) -> str:
    """Return a parent-facing rating label."""

    labels = {
        "worked_well": "Worked well",
        "helped_somewhat": "Helped somewhat",
        "not_relevant": "Not relevant",
        "did_not_work_well": "Did not work well",
    }

    return labels.get(
        rating,
        rating.replace(
            "_",
            " ",
        ).title(),
    )


def clean_strategy_title(
    title: str | None,
) -> str:
    """Remove trailing age information from summary prose."""

    return re.sub(
        r"\s*\(Ages?[^)]*\)\s*$",
        "",
        clean_text(title),
        flags=re.IGNORECASE,
    ).strip()


def readable_list(
    values: Sequence[str],
) -> str:
    """Join a short list into readable prose."""

    clean_values = [
        html.escape(
            clean_text(value)
        )
        for value in values
        if clean_text(value)
    ]

    if not clean_values:
        return ""

    if len(clean_values) == 1:
        return clean_values[0]

    if len(clean_values) == 2:
        return (
            f"{clean_values[0]} and {clean_values[1]}"
        )

    return (
        ", ".join(
            clean_values[:-1]
        )
        + f", and {clean_values[-1]}"
    )


def build_strategy_response_html(
    response: Mapping[str, Any],
) -> str:
    """Render the source-backed strategy API result for Joey's bubble."""

    outcome = str(
        response.get(
            "outcome",
            "",
        )
    )

    if outcome in {
        "safety_limited",
        "abstained",
    }:
        return html.escape(
            str(
                response.get(
                    "message",
                    "Joey could not provide a strategy result.",
                )
            )
        )

    strategies = response.get(
        "strategies",
        [],
    )

    if not isinstance(
        strategies,
        list,
    ) or not strategies:
        return html.escape(
            str(
                response.get(
                    "message",
                    "No source-backed strategies were returned.",
                )
            )
        )

    titles = [
        clean_strategy_title(
            str(
                item.get(
                    "strategy_title",
                    "",
                )
            )
        )
        for item in strategies
        if isinstance(
            item,
            Mapping,
        )
    ]

    introduction = (
        "Based on what you asked and the relevant confirmed "
        "background available to this prototype, the strongest "
        "source-backed options focus on "
        f"{readable_list(titles)}."
    )

    response_parts = [
        introduction
    ]

    history_notes = [
        str(
            item.get(
                "history_note",
                "",
            )
        ).lower()
        for item in strategies
        if isinstance(
            item,
            Mapping,
        )
    ]

    if any(
        "already recorded as active"
        in note
        for note in history_notes
    ):
        response_parts.append(
            "One of these options is already recorded as active, "
            "so reviewing how it is currently being used may be useful."
        )

    if any(
        (
            "helped somewhat" in note
            or "worked well" in note
        )
        for note in history_notes
    ):
        response_parts.append(
            "Previous confirmed feedback also indicates that at "
            "least one related approach was reported to help."
        )

    strategy_html: list[str] = []

    for index, item in enumerate(
        strategies,
        start=1,
    ):
        if not isinstance(
            item,
            Mapping,
        ):
            continue

        strategy_code = clean_text(
            str(
                item.get(
                    "strategy_code",
                    "",
                )
            )
        )
        strategy_title = clean_text(
            str(
                item.get(
                    "strategy_title",
                    "",
                )
            )
        )
        title = (
            f"{strategy_code}: {strategy_title}"
            if strategy_code
            else (
                strategy_title
                or "Relevant support strategy"
            )
        )

        passage = clean_text(
            str(
                item.get(
                    "passage",
                    "",
                )
            )
        )
        passage_preview = (
            passage
            if len(passage) <= 360
            else (
                passage[:360]
                .rsplit(
                    " ",
                    maxsplit=1,
                )[0]
                + "..."
            )
        )
        history_note = clean_text(
            str(
                item.get(
                    "history_note",
                    "",
                )
            )
        )
        history_sentence = ""

        if (
            history_note
            and "new strategy option"
            not in history_note.lower()
        ):
            history_sentence = (
                "<br><em>"
                f"{html.escape(history_note)}"
                "</em>"
            )

        collection_title = clean_text(
            str(
                item.get(
                    "collection_title",
                    "",
                )
            )
        )

        strategy_html.append(
            '<div class="joey-strategy">'
            f"<strong>{index}. {html.escape(title)}</strong><br>"
            f"{html.escape(passage_preview)}"
            f"{history_sentence}"
            '<div class="joey-source">'
            "Source: "
            f"{html.escape(collection_title)}"
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
            html.escape(
                part
            )
            for part in response_parts
        )
        + "</p>"
        + "".join(
            strategy_html
        )
    )


def build_strategy_feedback_prompt(
    strategy_count: int,
) -> str:
    """Explain the existing chat-based feedback format."""

    strategy_word = (
        "strategy"
        if strategy_count == 1
        else "strategies"
    )

    return (
        f"I displayed {strategy_count} {strategy_word}. "
        "To record feedback, reply with the strategy number and "
        "one of: <strong>worked well</strong>, "
        "<strong>helped somewhat</strong>, "
        "<strong>not relevant</strong>, or "
        "<strong>did not work well</strong>. "
        "For example: <strong>1 worked well</strong>. "
        "You can also ask another strategy question."
    )
