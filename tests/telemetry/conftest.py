from uuid import UUID

import pytest
from opentelemetry.test.globals_test import (
    reset_logging_globals,
    reset_metrics_globals,
    reset_trace_globals,
)

ACCOUNT_ID = UUID("11111111-1111-1111-1111-111111111111")
WORKSPACE_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def telemetry_account_id():
    return ACCOUNT_ID


@pytest.fixture
def telemetry_workspace_id():
    return WORKSPACE_ID


@pytest.fixture(autouse=True)
def reset_otel_globals():
    yield

    reset_logging_globals()
    reset_metrics_globals()
    reset_trace_globals()
