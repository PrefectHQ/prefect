import re

import pendulum
import pytest
import respx
from httpx import Response

from prefect import flow
from prefect.client.utilities import (
    DeploymentTimeout,
    InvalidOrionError,
    MissingFlowRunError,
    run_deployment,
    schedule_deployment,
)
from prefect.deployments import Deployment
from prefect.orion.schemas import states
from prefect.settings import PREFECT_API_URL
from prefect.testing.cli import invoke_and_assert


@flow
def ad_hoc_flow():
    pass


@pytest.fixture
def dep_path():
    return "./dog.py"


@pytest.fixture
def patch_import(monkeypatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    monkeypatch.setattr("prefect.utilities.importtools.import_object", lambda path: fn)


@pytest.fixture
def test_deployment(patch_import, tmp_path):
    d = Deployment(
        name="TEST",
        flow_name="fn",
    )
    deployment_id = d.apply()

    invoke_and_assert(
        [
            "deployment",
            "build",
            "fake-path.py:fn",
            "-n",
            "TEST",
            "-o",
            str(tmp_path / "test.yaml"),
            "--apply",
        ],
        expected_code=0,
        expected_output_contains=[
            f"Deployment '{d.flow_name}/{d.name}' successfully created with id '{deployment_id}'."
        ],
        temp_dir=tmp_path,
    )
    return d


class TestRunDeployment:
    @pytest.mark.parametrize(
        "terminal_state", list(sorted(s.name for s in states.TERMINAL_STATES))
    )
    def test_running_a_deployment_blocks_until_termination(
        self,
        test_deployment,
        use_hosted_orion,
        terminal_state,
    ):
        d = test_deployment

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=False
        ) as router:
            poll_responses = [
                Response(200, json={"state": {"type": "PENDING"}}),
                Response(200, json={"state": {"type": "RUNNING"}}),
                Response(200, json={"state": {"type": terminal_state}}),
            ]

            router.post(
                f"/deployments/name/{d.flow_name}/{d.name}/schedule_flow_run"
            ).pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(side_effect=poll_responses)

            assert (
                run_deployment(f"{d.flow_name}/{d.name}", max_polls=5, poll_interval=0)
                == terminal_state
            ), "run_deployment does not exit on {terminal_state}"
            assert len(flow_polls.calls) == 3

    def test_api_url_must_be_configured(
        self,
        test_deployment,
    ):
        d = test_deployment
        with pytest.raises(InvalidOrionError):
            run_deployment(f"{d.flow_name}/{d.name}", max_polls=3, poll_interval=0)

    def test_run_deployment_raises_on_polling_errors(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d = test_deployment

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=False
        ) as router:
            router.post(
                f"/deployments/name/{d.flow_name}/{d.name}/schedule_flow_run"
            ).pass_through()
            router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(return_value=Response(200, json=dict(foo="bar")))

            with pytest.raises(MissingFlowRunError):
                run_deployment(f"{d.flow_name}/{d.name}", max_polls=3, poll_interval=0)

    def test_running_a_raises_on_max_polls(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d = test_deployment

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=False
        ) as router:
            router.post(
                f"/deployments/name/{d.flow_name}/{d.name}/schedule_flow_run"
            ).pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(return_value=Response(200, json={"state": {"type": "SCHEDULED"}}))

            with pytest.raises(DeploymentTimeout):
                assert run_deployment(
                    f"{d.flow_name}/{d.name}", max_polls=5, poll_interval=0
                )
            assert len(flow_polls.calls) == 5


class TestScheduleDeployment:
    async def test_schedule_deployment_schedules_immediately_by_default(
        self, test_deployment, use_hosted_orion, orion_client
    ):
        d = test_deployment
        scheduled_time = pendulum.now()
        flow_run_id = schedule_deployment(f"{d.flow_name}/{d.name}")
        flow_run = await orion_client.read_flow_run(flow_run_id)
        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    async def test_schedule_deployment_accepts_custom_scheduled_time(
        self, test_deployment, use_hosted_orion, orion_client
    ):
        d = test_deployment
        scheduled_time = pendulum.now() + pendulum.Duration(minutes=5)
        flow_run_id = schedule_deployment(f"{d.flow_name}/{d.name}", scheduled_time)
        flow_run = await orion_client.read_flow_run(flow_run_id)
        assert (flow_run.expected_start_time - scheduled_time).total_seconds() == 0

    async def test_schedule_deployment_accepts_override_parameters(
        self, test_deployment, use_hosted_orion, orion_client
    ):
        d = test_deployment
        flow_run_id = schedule_deployment(
            f"{d.flow_name}/{d.name}", parameters={"a funky": "parameter"}
        )
        flow_run = await orion_client.read_flow_run(flow_run_id)
        assert flow_run.parameters["a funky"] == "parameter"

    async def test_schedule_deployment_run_is_not_auto_scheduled(
        self, test_deployment, use_hosted_orion, orion_client
    ):
        d = test_deployment
        flow_run_id = schedule_deployment(
            f"{d.flow_name}/{d.name}", parameters={"a funky": "parameter"}
        )
        flow_run = await orion_client.read_flow_run(flow_run_id)
        assert not flow_run.auto_scheduled
