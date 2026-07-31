"""HTTP client used by the Hey Joey Streamlit frontend."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import httpx

from app.settings import load_settings


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 15.0
STRATEGY_SEARCH_TIMEOUT_SECONDS = 120.0


class HeyJoeyApiError(RuntimeError):
    """Base exception for controlled frontend API failures."""


class ApiUnavailableError(HeyJoeyApiError):
    """Raised when the FastAPI service cannot be reached."""


class ApiTimeoutError(HeyJoeyApiError):
    """Raised when a running backend takes longer than the request limit."""


class ApiResponseError(HeyJoeyApiError):
    """Raised when FastAPI returns a non-success status."""

    def __init__(
        self,
        status_code: int,
        detail: str,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(
            f"Hey Joey API returned {status_code}: {detail}"
        )


class InvalidApiResponseError(HeyJoeyApiError):
    """Raised when the backend response is not a JSON object."""


def resolve_api_base_url(
    value: str | None = None,
) -> str:
    """Resolve and normalise the configured FastAPI base URL."""

    raw_value = (
        value
        if value is not None
        else load_settings().api_base_url
    )
    clean = str(raw_value or "").strip().rstrip("/")

    if not clean:
        return DEFAULT_API_BASE_URL

    return clean


class HeyJoeyApiClient:
    """Small typed wrapper around Joey's local HTTP endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = resolve_api_base_url(
            base_url
        )
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""

        self._client.close()

    def __enter__(
        self,
    ) -> "HeyJoeyApiClient":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()

    @staticmethod
    def _error_detail(
        response: httpx.Response,
    ) -> str:
        """Extract a readable FastAPI error detail."""

        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or "The backend returned an unknown error."

        if isinstance(payload, Mapping):
            detail = payload.get(
                "detail"
            )

            if isinstance(detail, str):
                return detail

            if isinstance(detail, Sequence) and not isinstance(
                detail,
                (str, bytes),
            ):
                messages: list[str] = []

                for item in detail:
                    if isinstance(item, Mapping):
                        message = str(
                            item.get(
                                "msg",
                                item,
                            )
                        ).strip()
                    else:
                        message = str(item).strip()

                    if message:
                        messages.append(message)

                if messages:
                    return "; ".join(messages)

        return str(payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Send one request and validate the shared JSON contract."""

        try:
            response = self._client.request(
                method,
                path,
                json=(
                    dict(json_body)
                    if json_body is not None
                    else None
                ),
                params=(
                    dict(params)
                    if params is not None
                    else None
                ),
                timeout=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else self._client.timeout
                ),
            )
        except httpx.TimeoutException as error:
            raise ApiTimeoutError(
                "The FastAPI backend is running, but the request took "
                "longer than expected. The first strategy search may "
                "need extra time while the local semantic model loads. "
                "Please wait for model loading to finish and try again."
            ) from error
        except (
            httpx.NetworkError,
            httpx.RequestError,
        ) as error:
            raise ApiUnavailableError(
                "The FastAPI backend is unavailable. Start it with "
                "'python -m uvicorn api.main:app --reload' and then "
                "reload Streamlit."
            ) from error

        if response.is_error:
            raise ApiResponseError(
                response.status_code,
                self._error_detail(
                    response
                ),
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise InvalidApiResponseError(
                "The FastAPI backend returned invalid JSON."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise InvalidApiResponseError(
                "The FastAPI backend response must be a JSON object."
            )

        return dict(payload)

    def health(
        self,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/health",
        )

    def create_record_session(
        self,
        note: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/record/sessions",
            json_body={
                "note": note,
            },
        )

    def get_record_session(
        self,
        session_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v1/record/sessions/{session_id}",
        )

    def submit_record_message(
        self,
        session_id: int,
        message: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            (
                "/api/v1/record/sessions/"
                f"{session_id}/messages"
            ),
            json_body={
                "message": message,
            },
        )

    def confirm_record_session(
        self,
        session_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            (
                "/api/v1/record/sessions/"
                f"{session_id}/confirm"
            ),
        )

    def reject_record_session(
        self,
        session_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            (
                "/api/v1/record/sessions/"
                f"{session_id}/reject"
            ),
        )

    def search_strategies(
        self,
        question: str,
        *,
        top_k: int = 3,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/strategies/search",
            json_body={
                "question": question,
                "top_k": top_k,
            },
            timeout_seconds=(
                STRATEGY_SEARCH_TIMEOUT_SECONDS
            ),
        )

    def get_strategy_search(
        self,
        search_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v1/strategies/searches/{search_id}",
        )

    def submit_strategy_feedback(
        self,
        *,
        search_id: int,
        strategy_rank: int,
        rating: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/strategies/feedback",
            json_body={
                "search_id": search_id,
                "strategy_rank": strategy_rank,
                "rating": rating,
                "comment": comment,
            },
        )

    def create_conversation(
        self,
        *,
        workflow: str,
        greeting: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/conversations/sessions",
            json_body={
                "workflow": workflow,
                "greeting": greeting,
                "metadata": dict(
                    metadata or {}
                ),
            },
        )

    def get_latest_conversation(
        self,
        workflow: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/conversations/sessions/latest",
            params={
                "workflow": workflow,
            },
        )

    def get_conversation(
        self,
        session_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            (
                "/api/v1/conversations/sessions/"
                f"{session_id}"
            ),
        )

    def append_conversation_exchange(
        self,
        *,
        session_id: int,
        user_content: str,
        user_message_type: str,
        assistant_messages: Sequence[str],
        assistant_message_type: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "user_content": user_content,
            "user_message_type": user_message_type,
            "assistant_messages": list(
                assistant_messages
            ),
            "assistant_message_type": (
                assistant_message_type
            ),
        }

        if metadata is not None:
            body["metadata"] = dict(
                metadata
            )

        return self._request(
            "POST",
            (
                "/api/v1/conversations/sessions/"
                f"{session_id}/exchanges"
            ),
            json_body=body,
        )
