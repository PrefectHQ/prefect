"""
Tests for worker attribution environment variables.
"""

from unittest import mock
from uuid import uuid4

from prefect.workers.base import BaseJobConfiguration


class TestBaseAttributionEnvironment:
    """Tests for the _base_attribution_environment method."""

    def test_returns_empty_dict_when_no_info(self):
        """When no info is provided, should return empty dict."""
        env = BaseJobConfiguration._base_attribution_environment()
        assert env == {}

    def test_includes_worker_id_when_provided(self):
        """Worker ID should be included in environment."""
        worker_id = uuid4()
        env = BaseJobConfiguration._base_attribution_environment(worker_id=worker_id)
        assert env["PREFECT__WORKER_ID"] == str(worker_id)

    def test_includes_worker_name_when_provided(self):
        """Worker name should be included in environment."""
        env = BaseJobConfiguration._base_attribution_environment(
            worker_name="test-worker"
        )
        assert env["PREFECT__WORKER_NAME"] == "test-worker"

    def test_includes_flow_id_from_flow_run(self):
        """Flow ID should be included from flow_run."""
        from prefect.client.schemas import FlowRun

        flow_id = uuid4()
        flow_run = FlowRun(id=uuid4(), name="test-run", flow_id=flow_id)
        env = BaseJobConfiguration._base_attribution_environment(flow_run=flow_run)
        assert env["PREFECT__FLOW_ID"] == str(flow_id)

    def test_includes_flow_name_from_flow(self):
        """Flow name should be included from flow object."""
        mock_flow = mock.MagicMock()
        mock_flow.name = "my-flow"
        env = BaseJobConfiguration._base_attribution_environment(flow=mock_flow)
        assert env["PREFECT__FLOW_NAME"] == "my-flow"

    def test_includes_deployment_id_from_flow_run(self):
        """Deployment ID should be included from flow_run."""
        from prefect.client.schemas import FlowRun

        deployment_id = uuid4()
        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=uuid4(),
            deployment_id=deployment_id,
        )
        env = BaseJobConfiguration._base_attribution_environment(flow_run=flow_run)
        assert env["PREFECT__DEPLOYMENT_ID"] == str(deployment_id)

    def test_includes_deployment_name_from_deployment(self):
        """Deployment name should be included from deployment object."""
        mock_deployment = mock.MagicMock()
        mock_deployment.name = "my-deployment"
        env = BaseJobConfiguration._base_attribution_environment(
            deployment=mock_deployment
        )
        assert env["PREFECT__DEPLOYMENT_NAME"] == "my-deployment"

    def test_includes_all_when_provided(self):
        """All attribution env vars should be included when all info is provided."""
        from prefect.client.schemas import FlowRun

        worker_id = uuid4()
        flow_id = uuid4()
        deployment_id = uuid4()

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=flow_id,
            deployment_id=deployment_id,
        )
        mock_flow = mock.MagicMock()
        mock_flow.name = "my-flow"
        mock_deployment = mock.MagicMock()
        mock_deployment.name = "my-deployment"

        env = BaseJobConfiguration._base_attribution_environment(
            flow_run=flow_run,
            deployment=mock_deployment,
            flow=mock_flow,
            worker_id=worker_id,
            worker_name="test-worker",
        )
        assert env["PREFECT__WORKER_ID"] == str(worker_id)
        assert env["PREFECT__WORKER_NAME"] == "test-worker"
        assert env["PREFECT__FLOW_ID"] == str(flow_id)
        assert env["PREFECT__FLOW_NAME"] == "my-flow"
        assert env["PREFECT__DEPLOYMENT_ID"] == str(deployment_id)
        assert env["PREFECT__DEPLOYMENT_NAME"] == "my-deployment"

    def test_none_worker_id_not_included(self):
        """When worker_id is None, it should not be in the environment."""
        env = BaseJobConfiguration._base_attribution_environment(
            worker_id=None, worker_name="test-worker"
        )
        assert "PREFECT__WORKER_ID" not in env
        assert env["PREFECT__WORKER_NAME"] == "test-worker"


class TestPrepareForFlowRun:
    """Tests for prepare_for_flow_run including attribution."""

    def test_includes_attribution_environment_variables(self):
        """Attribution environment variables should be included in the job configuration."""
        from prefect.client.schemas import FlowRun

        config = BaseJobConfiguration(env={})
        worker_id = uuid4()
        worker_name = "test-worker"
        flow_id = uuid4()

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=flow_id,
        )

        mock_flow = mock.MagicMock()
        mock_flow.name = "test-flow"

        config.prepare_for_flow_run(
            flow_run=flow_run,
            flow=mock_flow,
            worker_id=worker_id,
            worker_name=worker_name,
        )

        assert config.env["PREFECT__WORKER_ID"] == str(worker_id)
        assert config.env["PREFECT__WORKER_NAME"] == worker_name
        assert config.env["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)
        assert config.env["PREFECT__FLOW_ID"] == str(flow_id)
        assert config.env["PREFECT__FLOW_NAME"] == "test-flow"

    def test_includes_deployment_info(self):
        """Deployment info should be included in the job configuration."""
        from prefect.client.schemas import FlowRun

        config = BaseJobConfiguration(env={})
        deployment_id = uuid4()

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=uuid4(),
            deployment_id=deployment_id,
        )

        mock_deployment = mock.MagicMock()
        mock_deployment.name = "test-deployment"

        config.prepare_for_flow_run(
            flow_run=flow_run,
            deployment=mock_deployment,
        )

        assert config.env["PREFECT__DEPLOYMENT_ID"] == str(deployment_id)
        assert config.env["PREFECT__DEPLOYMENT_NAME"] == "test-deployment"

    def test_backward_compatible_without_worker_id(self):
        """Should work without worker_id for backward compatibility."""
        from prefect.client.schemas import FlowRun

        config = BaseJobConfiguration(env={})

        flow_run = FlowRun(
            id=uuid4(),
            name="test-run",
            flow_id=uuid4(),
        )

        config.prepare_for_flow_run(
            flow_run=flow_run,
            worker_name="test-worker",
        )

        assert "PREFECT__WORKER_ID" not in config.env
        assert config.env["PREFECT__WORKER_NAME"] == "test-worker"
        assert config.env["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)
