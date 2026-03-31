"""
Tests for worker attribution environment variables.
"""

from __future__ import annotations

import os
from unittest import mock
from uuid import uuid4

from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult


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


class _TestWorker(BaseWorker):
    type: str = "test-attribution"
    job_configuration = BaseJobConfiguration

    async def run(self) -> BaseWorkerResult:
        pass


class TestWorkerSelfAttribution:
    """Tests that the worker sets attribution env vars in its own process."""

    async def test_setup_sets_worker_name_env_var(self):
        """Worker name should be set in os.environ during setup."""
        worker = _TestWorker(work_pool_name="test-pool", name="my-test-worker")

        with mock.patch.dict(os.environ, {}, clear=False):
            # Remove any pre-existing value
            os.environ.pop("PREFECT__WORKER_NAME", None)

            with mock.patch.object(worker, "sync_with_backend"):
                with mock.patch("prefect.workers.base.get_client") as mock_get_client:
                    mock_client = mock.AsyncMock()
                    mock_get_client.return_value = mock_client
                    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

                    await worker.setup()

            assert os.environ.get("PREFECT__WORKER_NAME") == "my-test-worker"

    async def test_sync_with_backend_sets_worker_id_env_var(self):
        """Worker ID should be set in os.environ when backend returns an ID."""
        worker = _TestWorker(work_pool_name="test-pool", name="my-test-worker")
        remote_id = uuid4()

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PREFECT__WORKER_ID", None)

            with mock.patch.object(worker, "_update_local_work_pool_info"):
                with mock.patch.object(
                    worker, "_send_worker_heartbeat", return_value=remote_id
                ):
                    await worker.sync_with_backend()

            assert os.environ.get("PREFECT__WORKER_ID") == str(remote_id)
            assert worker.backend_id == remote_id

    async def test_sync_with_backend_does_not_set_worker_id_when_none(self):
        """Worker ID env var should not be set when heartbeat returns None."""
        worker = _TestWorker(work_pool_name="test-pool", name="my-test-worker")

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PREFECT__WORKER_ID", None)

            with mock.patch.object(worker, "_update_local_work_pool_info"):
                with mock.patch.object(
                    worker, "_send_worker_heartbeat", return_value=None
                ):
                    await worker.sync_with_backend()

            assert "PREFECT__WORKER_ID" not in os.environ

    async def test_teardown_cleans_up_env_vars(self):
        """Teardown should remove attribution env vars from os.environ."""
        worker = _TestWorker(work_pool_name="test-pool", name="my-test-worker")
        worker_id = uuid4()
        worker.backend_id = worker_id

        with mock.patch.dict(
            os.environ,
            {
                "PREFECT__WORKER_NAME": "my-test-worker",
                "PREFECT__WORKER_ID": str(worker_id),
            },
            clear=False,
        ):
            await worker.teardown(None, None, None)

            assert "PREFECT__WORKER_NAME" not in os.environ
            assert "PREFECT__WORKER_ID" not in os.environ

    async def test_teardown_does_not_remove_other_workers_env_vars(self):
        """Teardown should not remove env vars belonging to a different worker."""
        worker = _TestWorker(work_pool_name="test-pool", name="my-test-worker")
        worker.backend_id = uuid4()

        other_worker_name = "other-worker"
        other_worker_id = str(uuid4())

        with mock.patch.dict(
            os.environ,
            {
                "PREFECT__WORKER_NAME": other_worker_name,
                "PREFECT__WORKER_ID": other_worker_id,
            },
            clear=False,
        ):
            await worker.teardown(None, None, None)

            assert os.environ["PREFECT__WORKER_NAME"] == other_worker_name
            assert os.environ["PREFECT__WORKER_ID"] == other_worker_id

    async def test_teardown_safe_when_env_vars_not_set(self):
        """Teardown should not raise if env vars were never set."""
        worker = _TestWorker(work_pool_name="test-pool", name="my-test-worker")

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PREFECT__WORKER_NAME", None)
            os.environ.pop("PREFECT__WORKER_ID", None)

            # Should not raise
            await worker.teardown(None, None, None)
