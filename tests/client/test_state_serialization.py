"""
Tests for state serialization, specifically around the defer_build=True
behavior in PrefectBaseModel that can cause MockValSer errors.

Regression test for: TypeError: 'MockValSer' object cannot be converted to 'SchemaSerializer'

Root cause: PrefectBaseModel has defer_build=True, and when FlowRun.model_validate()
is called, pydantic rebuilds FlowRun but NOT nested models like StateDetails.
StateDetails stays incomplete with MockValSer as its serializer, causing
model_dump(serialize_as_any=True) to fail.
"""

import subprocess
import sys
from uuid import uuid4

import pytest
from pydantic._internal._mock_val_ser import MockValSer

from prefect.client.schemas.objects import FlowRun, StateDetails, StateType
from prefect.states import to_state_create


class TestStateSerializationWithDeferBuild:
    """
    Tests that verify state serialization works correctly despite defer_build=True.
    """

    def test_state_create_serialization_in_fresh_process(self):
        """
        Regression test: StateCreate.model_dump(serialize_as_any=True) should work
        even when StateDetails hasn't been explicitly rebuilt.

        This test runs in a subprocess to ensure a fresh Python interpreter state,
        which is required to reproduce the defer_build issue.
        """
        # NOTE: This test must use subprocess with inline code because the bug only
        # manifests in a fresh Python process before any other imports trigger model
        # rebuilding. Module-level imports in THIS file would mask the bug.
        code = """
import sys
from uuid import uuid4

from prefect.client.schemas.objects import FlowRun, StateType
from prefect.states import to_state_create

# Simulate reading a FlowRun from the API (exactly what workers do)
flow_run_data = {
    "id": str(uuid4()),
    "name": "test-run",
    "flow_id": str(uuid4()),
    "state": {
        "type": "PENDING",
        "name": "Pending",
        "timestamp": "2024-01-01T00:00:00Z",
        "state_details": {"flow_run_id": str(uuid4())},
    },
}

flow_run = FlowRun.model_validate(flow_run_data)

# This is the code path from _mark_flow_run_as_cancelled
state_updates = {"name": "Cancelled", "type": StateType.CANCELLED}
state = flow_run.state.model_copy(update=state_updates)
state_create = to_state_create(state)

# This should NOT raise:
# TypeError: 'MockValSer' object cannot be converted to 'SchemaSerializer'
try:
    result = state_create.model_dump(mode="json", serialize_as_any=True)
    print("SUCCESS")
    sys.exit(0)
except TypeError as e:
    if "MockValSer" in str(e):
        print(f"MOCKVALSER_ERROR: {e}")
        sys.exit(1)
    raise
"""

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )

        # Check for the specific MockValSer error
        if "MOCKVALSER_ERROR" in result.stdout:
            pytest.fail(
                f"StateCreate serialization failed with MockValSer error. "
                f"This indicates StateDetails was not properly rebuilt. "
                f"Output: {result.stdout}{result.stderr}"
            )

        # Check for general failure
        if result.returncode != 0:
            pytest.fail(
                f"StateCreate serialization failed unexpectedly. "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )

        assert "SUCCESS" in result.stdout

    def test_state_details_model_rebuild_works(self):
        """Verify that explicitly calling model_rebuild() on StateDetails works."""
        # Force rebuild
        StateDetails.model_rebuild(force=True)

        # Should be complete after rebuild
        assert StateDetails.__pydantic_complete__ is True

        # Create and serialize
        sd = StateDetails(flow_run_id=uuid4())
        result = sd.model_dump(mode="json", serialize_as_any=True)

        assert "flow_run_id" in result

    def test_state_details_serializer_is_not_mock(self):
        """
        Verify that StateDetails has a proper serializer, not MockValSer.

        After any model operation that should trigger building, the serializer
        should be a SchemaSerializer, not MockValSer.
        """
        # Force rebuild to ensure it's built
        StateDetails.model_rebuild(force=True)

        assert not isinstance(StateDetails.__pydantic_serializer__, MockValSer), (
            "StateDetails.__pydantic_serializer__ should not be MockValSer after rebuild"
        )

    def test_flow_run_state_to_state_create_serialization(self):
        """
        Test the full flow: FlowRun -> State -> StateCreate -> model_dump.

        This is the exact code path used in worker cancellation.
        """
        flow_run_data = {
            "id": str(uuid4()),
            "name": "test-run",
            "flow_id": str(uuid4()),
            "state": {
                "type": "PENDING",
                "name": "Pending",
                "timestamp": "2024-01-01T00:00:00Z",
                "state_details": {"flow_run_id": str(uuid4())},
            },
        }

        flow_run = FlowRun.model_validate(flow_run_data)

        state_updates = {"name": "Cancelled", "type": StateType.CANCELLED}
        state = flow_run.state.model_copy(update=state_updates)
        state_create = to_state_create(state)

        # This should not raise
        result = state_create.model_dump(mode="json", serialize_as_any=True)

        assert result["type"] == "CANCELLED"
        assert result["name"] == "Cancelled"
        assert "state_details" in result
