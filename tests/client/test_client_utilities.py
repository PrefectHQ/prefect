import re
from uuid import uuid4

import pendulum
import pytest
import respx
from httpx import Response

from prefect import flow
from prefect.client.utilities import (
    run_deployment,
)
from prefect.deployments import Deployment
from prefect.exceptions import PrefectHTTPStatusError
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
    return d, deployment_id


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
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
        ) as router:
            poll_responses = [
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "PENDING"}}
                ),
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "RUNNING"}}
                ),
                Response(
                    200,
                    json={**mock_flowrun_response, "state": {"type": terminal_state}},
                ),
            ]

            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.get(re.compile("/flow_runs/.*")).mock(
                side_effect=poll_responses
            )

            assert (
                run_deployment(
                    f"{d.flow_name}/{d.name}", max_polls=5, poll_interval=0
                ).state.type
                == terminal_state
            ), "run_deployment does not exit on {terminal_state}"
            assert len(flow_polls.calls) == 3

    @pytest.mark.parametrize(
        "terminal_state", list(sorted(s.name for s in states.TERMINAL_STATES))
    )
    async def test_running_a_deployment_blocks_until_termination_async(
        self,
        test_deployment,
        use_hosted_orion,
        terminal_state,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        async with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
        ) as router:
            poll_responses = [
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "PENDING"}}
                ),
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "RUNNING"}}
                ),
                Response(
                    200,
                    json={**mock_flowrun_response, "state": {"type": terminal_state}},
                ),
            ]

            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.get(re.compile("/flow_runs/.*")).mock(
                side_effect=poll_responses
            )

            assert (
                await run_deployment(
                    f"{d.flow_name}/{d.name}", max_polls=5, poll_interval=0
                )
            ).state.type == terminal_state, (
                "run_deployment does not exit on {terminal_state}"
            )
            assert len(flow_polls.calls) == 3

    def test_ephemeral_api_works(
        self,
        test_deployment,
        orion_client,
    ):
        d, deployment_id = test_deployment

        assert run_deployment(
            f"{d.flow_name}/{d.name}", max_polls=5, poll_interval=0
        ).state.is_scheduled()

    def test_returns_flow_run_on_max_polls(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=True
        ) as router:
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(
                return_value=Response(
                    200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
                )
            )

            flow_run = run_deployment(
                f"{d.flow_name}/{d.name}", max_polls=5, poll_interval=0
            )
            assert len(flow_polls.calls) == 5
            assert flow_run.state.is_scheduled()

    def test_returns_flow_run_immediately_when_max_polls_is_zero(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
            assert_all_called=False,
        ) as router:
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(
                return_value=Response(
                    200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
                )
            )

            flow_run = run_deployment(
                f"{d.flow_name}/{d.name}", max_polls=0, poll_interval=0
            )
            assert len(flow_polls.calls) == 0
            assert flow_run.state.is_scheduled()

    def test_polls_indefinitely(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        class LotsOfPolls(Exception):
            pass

        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        side_effects = [
            Response(
                200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
            )
        ] * 99
        side_effects.append(Response(200, json={**mock_flowrun_response, "state": {"type": "COMPLETED"}}))

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
            assert_all_called=False,
        ) as router:
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(side_effect=side_effects)

            run_deployment(f"{d.flow_name}/{d.name}", max_polls=-1, poll_interval=0)
            assert len(flow_polls.calls) == 100
