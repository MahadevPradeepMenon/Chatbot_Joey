"""Regression checks for Hey Joey production configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.logging_config import JoeyJsonFormatter, redact_secrets
from app.settings import SettingsError, load_settings


# Resolve configuration and source files relative to the repository root so the
# regression checks behave consistently from local shells and CI runners.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Keep this regression module runnable as a standalone script without requiring an
# external testing framework.
def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# Centralise repository-file loading and fail clearly when a required production
# configuration or integration file is missing.
def read(path: str) -> str:
    target = PROJECT_ROOT / path
    if not target.exists():
        raise AssertionError(f"Required file is missing: {path}")
    return target.read_text(encoding="utf-8")


# Verify that an empty environment mapping produces the intended local-development
# defaults, including private local data, enabled docs and text logging.
def test_local_defaults() -> None:
    settings = load_settings({})
    assert_true(settings.environment == "local", "Local environment default failed.")
    assert_true(not settings.demo_mode, "Local mode unexpectedly enables demo mode.")
    assert_true(settings.data_policy == "local_private", "Local data policy failed.")
    assert_true(settings.docs_enabled, "Local API documentation should be enabled.")
    assert_true(settings.log_format == "text", "Local log format should be text.")


# Confirm that production mode defaults to the safer demonstration configuration:
# synthetic-only data, no private-data access, disabled docs and JSON logs.
def test_safe_production_defaults() -> None:
    settings = load_settings({"HEY_JOEY_ENVIRONMENT": "production"})
    assert_true(settings.demo_mode, "Production should default to demo mode.")
    assert_true(settings.synthetic_only, "Production should default to synthetic-only data.")
    assert_true(not settings.allow_private_data, "Private data must not be allowed by default.")
    assert_true(not settings.docs_enabled, "Production API docs should be disabled by default.")
    assert_true(settings.log_format == "json", "Production logs should default to JSON.")


# Ensure production cannot silently combine local-private data with demo mode off
# unless private-data access has been explicitly authorised.
def test_unsafe_production_private_data_rejection() -> None:
    try:
        load_settings(
            {
                "HEY_JOEY_ENVIRONMENT": "production",
                "HEY_JOEY_DEMO_MODE": "false",
                "HEY_JOEY_DATA_POLICY": "local_private",
            }
        )
    except SettingsError:
        return
    raise AssertionError("Unsafe production private-data mode was accepted.")


# Verify that an explicit production override for private data is accepted only when
# the dedicated permission flag is enabled and demo mode is disabled.
def test_explicit_production_private_data_decision() -> None:
    settings = load_settings(
        {
            "HEY_JOEY_ENVIRONMENT": "production",
            "HEY_JOEY_DEMO_MODE": "false",
            "HEY_JOEY_DATA_POLICY": "local_private",
            "HEY_JOEY_ALLOW_PRIVATE_DATA": "true",
            "HEY_JOEY_DOCS_ENABLED": "false",
        }
    )
    assert_true(settings.allow_private_data, "Explicit private-data decision was lost.")
    assert_true(not settings.demo_mode, "Private production mode must not be demo mode.")


# Exercise both structured JSON formatting and secret redaction so sensitive values
# are not emitted into production-style logs.
def test_json_logging_and_redaction() -> None:
    record = logging.LogRecord(
        name="hey_joey.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=super-secret-value",
        args=(),
        exc_info=None,
    )
    # Parse the formatted log back into JSON so level metadata and redacted message
    # content can be asserted directly.
    payload = json.loads(JoeyJsonFormatter().format(record))
    assert_true(payload["level"] == "INFO", "JSON log level is missing.")
    assert_true("super-secret-value" not in payload["message"], "Log secret was not redacted.")
    assert_true("[REDACTED]" in redact_secrets("password=abc123"), "Direct redaction failed.")


# Check the production Compose file for resource limits, privilege reduction,
# bounded logging, persistent data storage and synthetic-only operation.
def test_production_compose_controls() -> None:
    content = read("compose.production.yaml")
    for required in (
        "mem_limit:",
        "cpus:",
        "pids_limit:",
        "no-new-privileges:true",
        "cap_drop:",
        "max-size:",
        "max-file:",
        "joey_production_data",
        "synthetic_only",
    ):
        assert_true(required in content, f"Production Compose control is missing: {required}")


# Verify the example environment files document distinct local and production
# defaults, including the synthetic-only and disabled-docs production safeguards.
def test_environment_templates() -> None:
    local = read(".env.example")
    production = read(".env.production.example")
    assert_true("HEY_JOEY_ENVIRONMENT=local" in local, "Local environment template failed.")
    assert_true("HEY_JOEY_ENVIRONMENT=production" in production, "Production template failed.")
    assert_true("HEY_JOEY_DATA_POLICY=synthetic_only" in production, "Synthetic-only policy is missing.")
    assert_true("HEY_JOEY_DOCS_ENABLED=false" in production, "Production docs safeguard is missing.")


# Inspect key runtime modules to confirm central settings are actually consumed by
# the API, database dependencies, frontend API client and Streamlit warning layer.
def test_runtime_integration() -> None:
    api_main = read("api/main.py")
    dependencies = read("api/dependencies.py")
    client = read("app/api_client.py")
    frontend = read("app/streamlit_app.py")
    assert_true("get_settings()" in api_main, "API does not load central settings.")
    assert_true("get_settings().database_path" in dependencies, "Database path is not centralised.")
    assert_true("load_settings().api_base_url" in client, "Frontend API URL is not centralised.")
    assert_true("Synthetic demonstration mode is active" in frontend, "Demo warning is missing.")


def main() -> None:
    # Keep production-configuration checks in a fixed order for deterministic local
    # and CI progress output.
    tests = [
        ("local configuration defaults", test_local_defaults),
        ("safe production defaults", test_safe_production_defaults),
        ("unsafe production private-data rejection", test_unsafe_production_private_data_rejection),
        ("explicit production private-data decision", test_explicit_production_private_data_decision),
        ("JSON logging and secret redaction", test_json_logging_and_redaction),
        ("production container controls", test_production_compose_controls),
        ("local and production environment templates", test_environment_templates),
        ("central settings runtime integration", test_runtime_integration),
    ]
    passed = 0
    # Any failed assertion stops the module with a non-zero exit status that the
    # wider CI suite can detect.
    for label, test in tests:
        test()
        passed += 1
        print(f"[PASS] {label}")
    print("\nPRODUCTION CONFIGURATION TEST RESULTS")
    print("=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")


# Run the production-configuration regressions only when this module is executed directly.
if __name__ == "__main__":
    main()
