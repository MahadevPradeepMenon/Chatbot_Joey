"""Regression tests for the Streamlit HTTP integration boundary."""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from api.main import create_app
from app.streamlit_api_adapter import (
    RECORD_GREETING,
    STRATEGY_GREETING,
    build_strategy_response_html,
    normalise_api_messages,
    parse_strategy_feedback,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def assert_true(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def test_record_message_rendering() -> None:
    history = normalise_api_messages(
        [
            {
                "role": "user",
                "content": "<unsafe>",
                "message_type": "observation",
            },
            {
                "role": "assistant",
                "content": "<unsafe>",
                "message_type": "record_summary",
            },
            {
                "role": "assistant",
                "content": "endpoint wording",
                "message_type": "confirmation_prompt",
            },
        ],
        greeting=RECORD_GREETING,
        assistant_html=False,
    )

    assert_true(
        history[0]["content"]
        == RECORD_GREETING,
        "The record greeting was not prepended.",
    )
    assert_true(
        history[1]["content"]
        == "<unsafe>",
        "User content should remain plain for renderer escaping.",
    )
    assert_true(
        history[2]["content"]
        == "&lt;unsafe&gt;",
        "Record assistant content was not escaped.",
    )
    assert_true(
        "<strong>yes</strong>"
        in history[3]["content"],
        "The UI confirmation wording was not restored.",
    )


def test_strategy_html_preserved() -> None:
    history = normalise_api_messages(
        [
            {
                "role": "assistant",
                "content": (
                    '<div class="joey-strategy">Result</div>'
                ),
                "message_type": "strategy_response",
            }
        ],
        greeting=STRATEGY_GREETING,
        assistant_html=True,
    )

    assert_true(
        "joey-strategy"
        in history[-1]["content"],
        "Trusted strategy HTML was not preserved.",
    )


def test_feedback_parser() -> None:
    assert_true(
        parse_strategy_feedback(
            "1 worked well"
        )
        == (
            1,
            "worked_well",
        ),
        "Worked-well feedback was not converted.",
    )
    assert_true(
        parse_strategy_feedback(
            "2: did not work well"
        )
        == (
            2,
            "did_not_work_well",
        ),
        "Negative feedback was not converted.",
    )
    assert_true(
        parse_strategy_feedback(
            "What may help?"
        )
        is None,
        "A strategy question was mistaken for feedback.",
    )


def sample_strategy_response() -> dict[str, Any]:
    return {
        "outcome": "results",
        "message": "Joey found one strategy.",
        "strategies": [
            {
                "strategy_code": "SP-01",
                "strategy_title": (
                    "Sensory Processing Support"
                ),
                "passage": (
                    "Reduce sensory demand and offer a calmer space."
                ),
                "collection_title": (
                    "Sensory Processing"
                ),
                "history_note": (
                    "The latest confirmed feedback reported "
                    "that it worked well."
                ),
            }
        ],
    }


def test_strategy_html_builder() -> None:
    result = build_strategy_response_html(
        sample_strategy_response()
    )

    assert_true(
        "SP-01" in result,
        "The strategy code was not displayed.",
    )
    assert_true(
        "Source: Sensory Processing"
        in result,
        "The source collection was not displayed.",
    )
    assert_true(
        "worked well"
        in result,
        "The stored feedback history was not displayed.",
    )


def test_strategy_html_escapes_source_data() -> None:
    response = sample_strategy_response()
    response["strategies"][0][
        "strategy_title"
    ] = "<script>alert(1)</script>"

    result = build_strategy_response_html(
        response
    )

    assert_true(
        "<script>" not in result,
        "Strategy source data was not escaped.",
    )
    assert_true(
        "&lt;script&gt;"
        in result,
        "Escaped strategy source data was missing.",
    )


def test_safety_and_abstention_rendering() -> None:
    safety = build_strategy_response_html(
        {
            "outcome": "safety_limited",
            "message": "<b>Safety first</b>",
        }
    )
    abstained = build_strategy_response_html(
        {
            "outcome": "abstained",
            "message": "I could not find a reliable match.",
        }
    )

    assert_true(
        safety
        == "&lt;b&gt;Safety first&lt;/b&gt;",
        "The safety response was not escaped.",
    )
    assert_true(
        "reliable match"
        in abstained,
        "The abstention message was not preserved.",
    )


def test_conversation_ui_api_round_trip() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            Path(directory)
            / "stage5d_conversations.db"
        )
        application = create_app(
            database_path=database_path
        )

        with TestClient(
            application
        ) as client:
            created = client.post(
                "/api/v1/conversations/sessions",
                json={
                    "workflow": "ask_strategy",
                    "greeting": STRATEGY_GREETING,
                    "metadata": {},
                },
            )

            assert_true(
                created.status_code == 201,
                "The conversation session was not created.",
            )
            session_id = int(
                created.json()[
                    "session_id"
                ]
            )

            exchange = client.post(
                (
                    "/api/v1/conversations/sessions/"
                    f"{session_id}/exchanges"
                ),
                json={
                    "user_content": "What may help with noise?",
                    "user_message_type": "strategy_question",
                    "assistant_messages": [
                        "Source-backed response"
                    ],
                    "assistant_message_type": (
                        "strategy_response"
                    ),
                    "metadata": {
                        "pending_strategy_feedback": {
                            "search_id": 8,
                            "strategy_count": 3,
                        }
                    },
                },
            )

            assert_true(
                exchange.status_code == 200,
                "The conversation exchange was not stored.",
            )
            payload = exchange.json()
            assert_true(
                len(payload["messages"]) == 3,
                "Greeting, user and assistant messages were expected.",
            )

            latest = client.get(
                "/api/v1/conversations/sessions/latest",
                params={
                    "workflow": "ask_strategy",
                },
            )

            assert_true(
                latest.status_code == 200,
                "The latest conversation was not restored.",
            )
            assert_true(
                latest.json()["metadata"][
                    "pending_strategy_feedback"
                ]["search_id"]
                == 8,
                "The pending feedback metadata was not restored.",
            )


def test_streamlit_has_no_backend_imports() -> None:
    source_path = (
        PROJECT_ROOT
        / "app"
        / "streamlit_app.py"
    )
    tree = ast.parse(
        source_path.read_text(
            encoding="utf-8"
        )
    )
    imported_modules: set[str] = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )
        elif isinstance(
            node,
            ast.ImportFrom,
        ) and node.module:
            imported_modules.add(
                node.module
            )

    forbidden_prefixes = (
        "rag",
        "safety",
        "storage",
        "app.conversation_manager",
        "app.conversation_persistence",
        "app.extractor",
        "app.record_workflow_service",
        "app.strategy_workflow_service",
    )

    for module in imported_modules:
        assert_true(
            not module.startswith(
                forbidden_prefixes
            ),
            (
                "Streamlit still imports a backend module directly: "
                f"{module}"
            ),
        )

    assert_true(
        "app.api_client"
        in imported_modules,
        "Streamlit does not import the HTTP API client.",
    )


def main() -> None:
    tests = [
        (
            "record message rendering",
            test_record_message_rendering,
        ),
        (
            "strategy HTML preservation",
            test_strategy_html_preserved,
        ),
        (
            "strategy feedback parsing",
            test_feedback_parser,
        ),
        (
            "strategy response HTML",
            test_strategy_html_builder,
        ),
        (
            "strategy data escaping",
            test_strategy_html_escapes_source_data,
        ),
        (
            "safety and abstention rendering",
            test_safety_and_abstention_rendering,
        ),
        (
            "conversation UI API round trip",
            test_conversation_ui_api_round_trip,
        ),
        (
            "Streamlit HTTP boundary",
            test_streamlit_has_no_backend_imports,
        ),
    ]

    passed = 0

    for name, test in tests:
        test()
        passed += 1
        print(
            f"[PASS] {name}"
        )

    print(
        "\nSTREAMLIT API INTEGRATION TEST RESULTS"
    )
    print("=" * 60)
    print(
        f"Tests passed: {passed}/{len(tests)}"
    )


if __name__ == "__main__":
    main()
