"""Tests for async_dispatch migration in prefect-kubernetes.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from typing import Coroutine

import pytest
from prefect_kubernetes.jobs import KubernetesJob, KubernetesJobRun

from prefect import flow


@pytest.fixture
def mock_kubernetes_job(
    kubernetes_credentials,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_list_namespaced_pod,
    read_pod_logs,
    mock_delete_namespaced_job,
):
    """Create a KubernetesJob with mocked kubernetes API calls."""
    return KubernetesJob(
        credentials=kubernetes_credentials,
        v1_job={
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": "test-job"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "test", "image": "test:latest"}],
                        "restartPolicy": "Never",
                    }
                }
            },
        },
    )


class TestKubernetesJobTriggerAsyncDispatch:
    """Tests for KubernetesJob.trigger migrated from @sync_compatible to @async_dispatch."""

    def test_trigger_sync_context_returns_job_run_not_coroutine(
        self, mock_kubernetes_job
    ):
        """trigger must return KubernetesJobRun (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            result = mock_kubernetes_job.trigger()
            # The result inside the flow should be the actual value, not a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        job_run = test_flow()
        assert isinstance(job_run, KubernetesJobRun)

    async def test_trigger_async_context_works(self, mock_kubernetes_job):
        """trigger should work correctly in async context."""

        @flow
        async def test_flow():
            # In async context, @async_dispatch dispatches to async version
            result = await mock_kubernetes_job.atrigger()
            return result

        job_run = await test_flow()
        assert isinstance(job_run, KubernetesJobRun)

    def test_atrigger_is_available(self, mock_kubernetes_job):
        """atrigger should be available for direct async usage."""
        assert hasattr(mock_kubernetes_job, "atrigger")
        assert callable(mock_kubernetes_job.atrigger)


class TestKubernetesJobRunWaitForCompletionAsyncDispatch:
    """Tests for KubernetesJobRun.wait_for_completion async_dispatch migration."""

    def test_wait_for_completion_sync_context_returns_none_not_coroutine(
        self, mock_kubernetes_job
    ):
        """wait_for_completion must not return coroutine in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            job_run = mock_kubernetes_job.trigger()
            result = job_run.wait_for_completion()
            # The result should not be a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return job_run

        job_run = test_flow()
        assert isinstance(job_run, KubernetesJobRun)

    async def test_wait_for_completion_async_context_works(self, mock_kubernetes_job):
        """wait_for_completion should work correctly in async context."""

        @flow
        async def test_flow():
            job_run = await mock_kubernetes_job.atrigger()
            # In async context, @async_dispatch dispatches to async version
            await job_run.await_for_completion()
            return job_run

        job_run = await test_flow()
        assert isinstance(job_run, KubernetesJobRun)

    def test_await_for_completion_is_available(self, mock_kubernetes_job):
        """await_for_completion should be available for direct async usage."""

        @flow
        def test_flow():
            job_run = mock_kubernetes_job.trigger()
            assert hasattr(job_run, "await_for_completion")
            assert callable(job_run.await_for_completion)
            job_run.wait_for_completion()

        test_flow()


class TestKubernetesJobRunFetchResultAsyncDispatch:
    """Tests for KubernetesJobRun.fetch_result async_dispatch migration."""

    def test_fetch_result_sync_context_returns_value_not_coroutine(
        self, mock_kubernetes_job
    ):
        """fetch_result must return dict (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            job_run = mock_kubernetes_job.trigger()
            job_run.wait_for_completion()
            result = job_run.fetch_result()
            # The result should not be a coroutine
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, dict)

    async def test_fetch_result_async_context_works(self, mock_kubernetes_job):
        """fetch_result should work correctly in async context."""

        @flow
        async def test_flow():
            job_run = await mock_kubernetes_job.atrigger()
            await job_run.await_for_completion()
            # In async context, @async_dispatch dispatches to async version
            result = await job_run.afetch_result()
            return result

        result = await test_flow()
        assert isinstance(result, dict)

    def test_afetch_result_is_available(self, mock_kubernetes_job):
        """afetch_result should be available for direct async usage."""

        @flow
        def test_flow():
            job_run = mock_kubernetes_job.trigger()
            job_run.wait_for_completion()
            assert hasattr(job_run, "afetch_result")
            assert callable(job_run.afetch_result)

        test_flow()
