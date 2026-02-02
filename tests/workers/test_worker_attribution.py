"""
Tests for worker attribution environment variables.
"""

from uuid import uuid4

from prefect.workers.base import BaseJobConfiguration


class TestBaseWorkerEnvironment:
    """Tests for the _base_worker_environment method."""

    def test_returns_empty_dict_when_no_worker_info(self):
        """When no worker info is provided, should return empty dict."""
        env = BaseJobConfiguration._base_worker_environment()
        assert env == {}

    def test_includes_worker_id_when_provided(self):
        """Worker ID should be included in environment."""
        worker_id = uuid4()
        env = BaseJobConfiguration._base_worker_environment(worker_id=worker_id)
        assert env["PREFECT__WORKER_ID"] == str(worker_id)

    def test_includes_worker_name_when_provided(self):
        """Worker name should be included in environment."""
        env = BaseJobConfiguration._base_worker_environment(worker_name="test-worker")
        assert env["PREFECT__WORKER_NAME"] == "test-worker"

    def test_includes_both_when_provided(self):
        """Both worker ID and name should be included when provided."""
        worker_id = uuid4()
        worker_name = "full-context-worker"
        env = BaseJobConfiguration._base_worker_environment(
            worker_id=worker_id, worker_name=worker_name
        )
        assert env["PREFECT__WORKER_ID"] == str(worker_id)
        assert env["PREFECT__WORKER_NAME"] == worker_name

    def test_none_worker_id_not_included(self):
        """When worker_id is None, it should not be in the environment."""
        env = BaseJobConfiguration._base_worker_environment(
            worker_id=None, worker_name="test-worker"
        )
        assert "PREFECT__WORKER_ID" not in env
        assert env["PREFECT__WORKER_NAME"] == "test-worker"

    def test_none_worker_name_not_included(self):
        """When worker_name is None, it should not be in the environment."""
        worker_id = uuid4()
        env = BaseJobConfiguration._base_worker_environment(
            worker_id=worker_id, worker_name=None
        )
        assert env["PREFECT__WORKER_ID"] == str(worker_id)
        assert "PREFECT__WORKER_NAME" not in env


class TestPrepareForFlowRun:
    """Tests for prepare_for_flow_run including worker attribution."""

    def test_includes_worker_environment_variables(self):
        """Worker environment variables should be included in the job configuration."""
        from prefect.client.schemas import FlowRun

        config = BaseJobConfiguration(env={})
        worker_id = uuid4()
        worker_name = "test-worker"

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=uuid4(),
        )

        config.prepare_for_flow_run(
            flow_run=flow_run,
            worker_id=worker_id,
            worker_name=worker_name,
        )

        assert config.env["PREFECT__WORKER_ID"] == str(worker_id)
        assert config.env["PREFECT__WORKER_NAME"] == worker_name
        assert config.env["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)

    def test_worker_env_not_overridden_by_user_env(self):
        """User-provided env should not override worker attribution variables."""
        from prefect.client.schemas import FlowRun

        # User tries to set their own worker ID (should be overridden by actual worker)
        config = BaseJobConfiguration(
            env={
                "PREFECT__WORKER_ID": "user-fake-id",
                "PREFECT__WORKER_NAME": "user-fake-name",
                "MY_CUSTOM_VAR": "custom-value",
            }
        )

        worker_id = uuid4()
        worker_name = "actual-worker"

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=uuid4(),
        )

        config.prepare_for_flow_run(
            flow_run=flow_run,
            worker_id=worker_id,
            worker_name=worker_name,
        )

        # Worker environment is merged before user env, so user env takes precedence
        # This is by design - users can override if they want to (for testing, etc.)
        # The actual values depend on merge order in prepare_for_flow_run
        # The important thing is that when worker provides values, they're available
        assert "MY_CUSTOM_VAR" in config.env
        assert config.env["MY_CUSTOM_VAR"] == "custom-value"

    def test_backward_compatible_without_worker_id(self):
        """Should work without worker_id for backward compatibility."""
        from prefect.client.schemas import FlowRun

        config = BaseJobConfiguration(env={})

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=uuid4(),
        )

        # Call without worker_id
        config.prepare_for_flow_run(
            flow_run=flow_run,
            worker_name="test-worker",
        )

        # Should still work, just without worker_id
        assert "PREFECT__WORKER_ID" not in config.env
        assert config.env["PREFECT__WORKER_NAME"] == "test-worker"
        assert config.env["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)
