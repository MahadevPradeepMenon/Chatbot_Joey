"""Central environment-based configuration for Hey Joey."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENVIRONMENT_LOCAL = "local"
ENVIRONMENT_TEST = "test"
ENVIRONMENT_PRODUCTION = "production"
ALLOWED_ENVIRONMENTS = frozenset(
    {
        ENVIRONMENT_LOCAL,
        ENVIRONMENT_TEST,
        ENVIRONMENT_PRODUCTION,
    }
)

DATA_POLICY_LOCAL_PRIVATE = "local_private"
DATA_POLICY_SYNTHETIC_ONLY = "synthetic_only"
ALLOWED_DATA_POLICIES = frozenset(
    {
        DATA_POLICY_LOCAL_PRIVATE,
        DATA_POLICY_SYNTHETIC_ONLY,
    }
)

ALLOWED_LOG_LEVELS = frozenset(
    {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }
)
ALLOWED_LOG_FORMATS = frozenset(
    {
        "text",
        "json",
    }
)


class SettingsError(ValueError):
    """Raised when runtime configuration is missing or unsafe."""


@dataclass(frozen=True)
class JoeySettings:
    """Validated runtime settings shared by the API and frontend."""

    environment: str
    demo_mode: bool
    data_policy: str
    allow_private_data: bool
    data_dir: Path
    database_path: Path
    api_base_url: str
    log_level: str
    log_format: str
    docs_enabled: bool

    @property
    def is_production(self) -> bool:
        """Return whether production safeguards should be active."""

        return self.environment == ENVIRONMENT_PRODUCTION

    @property
    def synthetic_only(self) -> bool:
        """Return whether only synthetic demonstration data is allowed."""

        return self.data_policy == DATA_POLICY_SYNTHETIC_ONLY

    @property
    def environment_label(self) -> str:
        """Return a display-safe environment label."""

        return self.environment.replace("_", " ").title()


def _read(
    environ: Mapping[str, str],
    key: str,
    default: str,
) -> str:
    """Read and trim one environment value."""

    return str(
        environ.get(
            key,
            default,
        )
        or ""
    ).strip()


def _parse_bool(
    raw_value: str,
    *,
    key: str,
) -> bool:
    """Parse a strict boolean environment value."""

    normalised = raw_value.strip().lower()

    if normalised in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if normalised in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise SettingsError(
        f"{key} must be true or false."
    )


def _normalise_choice(
    raw_value: str,
    *,
    key: str,
    allowed: frozenset[str],
) -> str:
    """Normalise and validate one enumerated setting."""

    normalised = raw_value.strip().lower()

    if normalised not in allowed:
        choices = ", ".join(
            sorted(allowed)
        )
        raise SettingsError(
            f"{key} must be one of: {choices}."
        )

    return normalised


def _resolve_path(
    raw_value: str,
    *,
    default: Path,
) -> Path:
    """Resolve an absolute or project-relative path without creating it."""

    if not raw_value:
        return default.resolve()

    path = Path(raw_value).expanduser()

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve()


def _normalise_api_url(
    raw_value: str,
) -> str:
    """Validate and normalise the frontend-to-API base URL."""

    clean = raw_value.strip().rstrip("/")
    parsed = urlsplit(clean)

    if parsed.scheme not in {
        "http",
        "https",
    } or not parsed.netloc:
        raise SettingsError(
            "HEY_JOEY_API_URL must be an absolute HTTP or HTTPS URL."
        )

    if parsed.username or parsed.password:
        raise SettingsError(
            "HEY_JOEY_API_URL must not contain embedded credentials."
        )

    return clean


def load_settings(
    environ: Mapping[str, str] | None = None,
) -> JoeySettings:
    """Load and validate settings from one environment mapping."""

    values = os.environ if environ is None else environ

    environment = _normalise_choice(
        _read(
            values,
            "HEY_JOEY_ENVIRONMENT",
            ENVIRONMENT_LOCAL,
        ),
        key="HEY_JOEY_ENVIRONMENT",
        allowed=ALLOWED_ENVIRONMENTS,
    )
    production = (
        environment == ENVIRONMENT_PRODUCTION
    )

    demo_mode = _parse_bool(
        _read(
            values,
            "HEY_JOEY_DEMO_MODE",
            "true" if production else "false",
        ),
        key="HEY_JOEY_DEMO_MODE",
    )

    data_policy = _normalise_choice(
        _read(
            values,
            "HEY_JOEY_DATA_POLICY",
            (
                DATA_POLICY_SYNTHETIC_ONLY
                if demo_mode
                else DATA_POLICY_LOCAL_PRIVATE
            ),
        ),
        key="HEY_JOEY_DATA_POLICY",
        allowed=ALLOWED_DATA_POLICIES,
    )

    allow_private_data = _parse_bool(
        _read(
            values,
            "HEY_JOEY_ALLOW_PRIVATE_DATA",
            "false",
        ),
        key="HEY_JOEY_ALLOW_PRIVATE_DATA",
    )

    if demo_mode and data_policy != DATA_POLICY_SYNTHETIC_ONLY:
        raise SettingsError(
            "Demo mode requires HEY_JOEY_DATA_POLICY=synthetic_only."
        )

    if (
        production
        and data_policy == DATA_POLICY_LOCAL_PRIVATE
        and not allow_private_data
    ):
        raise SettingsError(
            "Production private-data mode requires an explicit "
            "HEY_JOEY_ALLOW_PRIVATE_DATA=true decision."
        )

    data_dir = _resolve_path(
        _read(
            values,
            "HEY_JOEY_DATA_DIR",
            "",
        ),
        default=PROJECT_ROOT / "data",
    )
    database_path = _resolve_path(
        _read(
            values,
            "HEY_JOEY_DATABASE_PATH",
            "",
        ),
        default=data_dir / "local" / "joey.db",
    )

    raw_api_base_url = _read(
        values,
        "HEY_JOEY_API_URL",
        "http://127.0.0.1:8000",
    )
    api_base_url = _normalise_api_url(
        raw_api_base_url
        or "http://127.0.0.1:8000"
    )

    log_level = _read(
        values,
        "HEY_JOEY_LOG_LEVEL",
        "INFO",
    ).upper()
    if log_level not in ALLOWED_LOG_LEVELS:
        raise SettingsError(
            "HEY_JOEY_LOG_LEVEL must be DEBUG, INFO, WARNING, "
            "ERROR or CRITICAL."
        )

    log_format = _normalise_choice(
        _read(
            values,
            "HEY_JOEY_LOG_FORMAT",
            "json" if production else "text",
        ),
        key="HEY_JOEY_LOG_FORMAT",
        allowed=ALLOWED_LOG_FORMATS,
    )

    docs_enabled = _parse_bool(
        _read(
            values,
            "HEY_JOEY_DOCS_ENABLED",
            "false" if production else "true",
        ),
        key="HEY_JOEY_DOCS_ENABLED",
    )

    return JoeySettings(
        environment=environment,
        demo_mode=demo_mode,
        data_policy=data_policy,
        allow_private_data=allow_private_data,
        data_dir=data_dir,
        database_path=database_path,
        api_base_url=api_base_url,
        log_level=log_level,
        log_format=log_format,
        docs_enabled=docs_enabled,
    )


@lru_cache(maxsize=1)
def get_settings() -> JoeySettings:
    """Return the process-wide validated settings instance."""

    return load_settings()


def reset_settings_cache() -> None:
    """Clear cached settings for isolated tests and controlled reloads."""

    get_settings.cache_clear()
