import re
import time
from typing import TYPE_CHECKING
from unittest import mock
from uuid import uuid4

import pendulum
import pytest
import respx
from httpx import Response

import prefect.client.schemas as client_schemas
from prefect import flow
from prefect.context import FlowRunContext
from prefect.exceptions import FlowRunWaitTimeout
from prefect.flow_runs import run_deployment, wait_for_flow_run
from prefect.server.schemas.core import TaskRunResult
from prefect.settings import PREFECT_API_URL
from prefect.states import Completed
from prefect.tasks import task
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


async def test_create_then_wait_for_flow_run(prefect_client):
    @flow
    def foo():
        pass

    flow_run = await prefect_client.create_flow_run(
        foo, name="petes-flow-run", state=Completed()
    )
    assert isinstance(flow_run, client_schemas.FlowRun)

    lookup = await wait_for_flow_run(flow_run.id, poll_interval=0)
    # Estimates will not be equal since time has passed
    assert lookup == flow_run
    assert flow_run.state.is_final()


async def test_create_then_wait_timeout(prefect_client):
    @flow
    def foo():
        time.sleep(9999)

    flow_run = await prefect_client.create_flow_run(
        foo,
        name="petes-flow-run",
    )
    assert isinstance(flow_run, client_schemas.FlowRun)

    with pytest.raises(FlowRunWaitTimeout):
        await wait_for_flow_run(flow_run.id, timeout=0)


class TestRunDeployment:
    @pytest.fixture
    async def test_deployment(self, prefect_client):
        flow_id = await prefect_client.create_flow_from_name("foo")

        deployment_id = await prefect_client.create_deployment(
            name="foo-deployment", flow_id=flow_id
        )
        deployment = await prefect_client.read_deployment(deployment_id)

        return deployment

    async def test_run_deployment_with_ephemeral_api(
        self, prefect_client, test_deployment
    ):
        deployment = test_deployment
        flow_run = await run_deployment(
            f"foo/{deployment.name}",
            timeout=0,
            poll_interval=0,
            client=prefect_client,
        )
        assert flow_run.deployment_id == deployment.id
        assert flow_run.state

    async def test_run_deployment_with_deployment_id_str(
        self,
        test_deployment,
        prefect_client,
    ):
        deployment = test_deployment

        flow_run = await run_deployment(
            f"{deployment.id}",
            timeout=0,
            poll_interval=0,
            client=prefect_client,
        )
        assert flow_run.deployment_id == deployment.id
        assert flow_run.state

    async def test_run_deployment_with_deployment_id_uuid(
        self,
        test_deployment,
        prefect_client,
    ):
        deployment = test_deployment

        flow_run = await run_deployment(
            deployment.id,
            timeout=0,
            poll_interval=0,
            client=prefect_client,
        )
        assert flow_run.deployment_id == deployment.id
        assert flow_run.state

    async def test_run_deployment_with_job_vars_creates_run_with_job_vars(
        self,
        test_deployment,
        prefect_client,
    ):
        # This can be removed once the flow run infra overrides is no longer an experiment
        deployment = test_deployment

        job_vars = {"foo": "bar"}
        flow_run = await run_deployment(
            deployment.id,
            timeout=0,
            job_variables=job_vars,
            client=prefect_client,
        )
        assert flow_run.job_variables == job_vars
        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.job_variables == job_vars

    def test_returns_flow_run_on_timeout(
        self,
        test_deployment,
        use_hosted_api_server,
    ):
        deployment = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=True
        ) as router:
            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
            router.get(f"/deployments/name/foo/{deployment.name}").pass_through()
            router.post(f"/deployments/{deployment.id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(
                return_value=Response(
                    200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
                )
            )

            flow_run = run_deployment(
                f"foo/{deployment.name}", timeout=1, poll_interval=0
            )
            assert len(flow_polls.calls) > 0
            assert flow_run.state

    async def test_returns_flow_run_immediately_when_timeout_is_zero(
        self,
        test_deployment,
        use_hosted_api_server,
    ):
        deployment = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
            assert_all_called=False,
        ) as router:
            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
            router.get(f"/deployments/name/foo/{deployment.name}").pass_through()
            router.post(f"/deployments/{deployment.id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(
                return_value=Response(
                    200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
                )
            )

            flow_run = await run_deployment(
                f"foo/{deployment.name}", timeout=0, poll_interval=0
            )
            assert len(flow_polls.calls) == 0
            assert flow_run.state.is_scheduled()

    def test_polls_indefinitely(
        self,
        test_deployment,
        use_hosted_api_server,
    ):
        deployment = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        side_effects = [
            Response(
                200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
            )
        ] * 99
        side_effects.append(
            Response(
                200, json={**mock_flowrun_response, "state": {"type": "COMPLETED"}}
            )
        )

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
            assert_all_called=False,
        ) as router:
            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
            router.get(f"/deployments/name/foo/{deployment.name}").pass_through()
            router.post(f"/deployments/{deployment.id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(side_effect=side_effects)

            run_deployment(f"foo/{deployment.name}", timeout=None, poll_interval=0)
            assert len(flow_polls.calls) == 100

    def test_schedules_immediately_by_default(
        self, test_deployment, use_hosted_api_server
    ):
        deployment = test_deployment

        scheduled_time = pendulum.now("UTC")
        flow_run = run_deployment(
            f"foo/{deployment.name}",
            timeout=0,
            poll_interval=0,
        )

        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    def test_accepts_custom_scheduled_time(
        self, test_deployment, use_hosted_api_server
    ):
        deployment = test_deployment

        scheduled_time = pendulum.now("UTC") + pendulum.Duration(minutes=5)
        flow_run = run_deployment(
            f"foo/{deployment.name}",
            scheduled_time=scheduled_time,
            timeout=0,
            poll_interval=0,
        )

        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    def test_custom_flow_run_names(self, test_deployment, use_hosted_api_server):
        deployment = test_deployment

        flow_run = run_deployment(
            f"foo/{deployment.name}",
            flow_run_name="a custom flow run name",
            timeout=0,
            poll_interval=0,
        )

        assert flow_run.name == "a custom flow run name"

    def test_accepts_tags(self, test_deployment):
        deployment = test_deployment

        flow_run = run_deployment(
            f"foo/{deployment.name}",
            tags=["I", "love", "prefect"],
            timeout=0,
            poll_interval=0,
        )

        assert sorted(flow_run.tags) == ["I", "love", "prefect"]

    def test_accepts_idempotency_key(self, test_deployment):
        deployment = test_deployment

        flow_run_a = run_deployment(
            f"foo/{deployment.name}",
            idempotency_key="12345",
            timeout=0,
            poll_interval=0,
        )

        flow_run_b = run_deployment(
            f"foo/{deployment.name}",
            idempotency_key="12345",
            timeout=0,
            poll_interval=0,
        )

        assert flow_run_a.id == flow_run_b.id

    async def test_links_to_parent_flow_run_when_used_in_flow_by_default(
        self, test_deployment, use_hosted_api_server, prefect_client: "PrefectClient"
    ):
        my_deployment = test_deployment

        @flow
        async def foo():
            return await run_deployment(
                f"foo/{my_deployment.name}",
                timeout=0,
                poll_interval=0,
            )

        parent_state = await foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await prefect_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.flow_run_id == parent_state.state_details.flow_run_id
        deployment_name = f"foo/{my_deployment.name}"
        assert isinstance(deployment_name, str)
        assert slugify(deployment_name) in task_run.task_key

    async def test_optionally_does_not_link_to_parent_flow_run_when_used_in_flow(
        self, test_deployment, use_hosted_api_server, prefect_client: "PrefectClient"
    ):
        deployment = test_deployment

        @flow
        async def foo():
            return await run_deployment(
                f"foo/{deployment.name}",
                timeout=0,
                poll_interval=0,
                as_subflow=False,
            )

        parent_state = await foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is None

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_links_to_parent_flow_run_when_used_in_task_without_flow_context(
        self, test_deployment, prefect_client
    ):
        """
        Regression test for deployments in a task on Dask and Ray task runners
        which do not have access to the flow run context - https://github.com/PrefectHQ/prefect/issues/9135
        """
        deployment = test_deployment

        @task
        async def yeet_deployment():
            with mock.patch.object(FlowRunContext, "get", return_value=None):
                assert FlowRunContext.get() is None
                result = await run_deployment(
                    f"foo/{deployment.name}",
                    timeout=0,
                    poll_interval=0,
                )
                return result

        @flow
        async def foo():
            return await yeet_deployment()

        parent_state = await foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await prefect_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.flow_run_id == parent_state.state_details.flow_run_id
        assert slugify(f"foo/{deployment.name}") in task_run.task_key

    async def test_tracks_dependencies_when_used_in_flow(
        self, test_deployment, use_hosted_api_server, prefect_client
    ):
        deployment = test_deployment

        @task
        def bar():
            return "hello-world!!"

        @flow
        async def foo():
            upstream_task_state = bar(return_state=True)
            upstream_result = await upstream_task_state.result()
            child_flow_run = await run_deployment(
                f"foo/{deployment.name}",
                timeout=0,
                poll_interval=0,
                parameters={"x": upstream_result},
            )
            return upstream_task_state, child_flow_run

        parent_state = await foo(return_state=True)
        upstream_task_state, child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await prefect_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.task_inputs == {
            "x": [
                TaskRunResult(
                    input_type="task_run",
                    id=upstream_task_state.state_details.task_run_id,
                )
            ]
        }
