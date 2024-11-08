from uuid import UUID

import pytest
from opentelemetry.test.globals_test import (
    reset_logging_globals,
    reset_metrics_globals,
    reset_trace_globals,
)

from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_EXPERIMENTS_TELEMETRY_ENABLED,
    temporary_settings,
)

ACCOUNT_ID = UUID("11111111-1111-1111-1111-111111111111")
WORKSPACE_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def telemetry_account_id():
    return ACCOUNT_ID


@pytest.fixture
def telemetry_workspace_id():
    return WORKSPACE_ID


@pytest.fixture
def enable_telemetry(telemetry_account_id: UUID, telemetry_workspace_id: UUID):
    with temporary_settings(
        {
            PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{telemetry_account_id}/workspaces/{telemetry_workspace_id}",
            PREFECT_API_KEY: "my-token",
            PREFECT_EXPERIMENTS_TELEMETRY_ENABLED: True,
        }
    ):
        yield


@pytest.fixture
def hosted_server_with_telemetry_enabled():
    with temporary_settings(
        {
            PREFECT_EXPERIMENTS_TELEMETRY_ENABLED: True,
            PREFECT_API_URL: "https://prefect.example.com/api",
        }
    ):
        yield


@pytest.fixture
def disable_telemetry():
    with temporary_settings({PREFECT_EXPERIMENTS_TELEMETRY_ENABLED: False}):
        yield


@pytest.fixture(autouse=True)
def reset_otel_globals():
    yield

    reset_logging_globals()
    reset_metrics_globals()
    reset_trace_globals()
