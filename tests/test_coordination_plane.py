import json
import re

import pytest
import respx
from httpx import Response

from prefect import flow
from prefect.coordination_plane import _minimal_client, run_deployment
from prefect.deployments import Deployment
from prefect.settings import PREFECT_API_URL, temporary_settings
from prefect.testing.cli import invoke_and_assert

TEST_ORION_URL = "https://mock-orion.prefect.io/api"


@flow
def my_flow():
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


@pytest.fixture
def hosted_orion(self):
    with temporary_settings(updates={PREFECT_API_URL: TEST_ORION_URL}):
        yield


def test_running_a_deployment_blocks_utnil_termination(
    test_deployment,
    use_hosted_orion,
    orion_client,
):
    d = test_deployment

    with respx.mock(
        base_url=PREFECT_API_URL.value(), assert_all_mocked=False
    ) as router:
        poll_responses = [
            Response(200, json={"state": {"type": "PENDING"}}),
            Response(200, json={"state": {"type": "RUNNING"}}),
            Response(200, json={"state": {"type": "COMPLETED"}}),
        ]

        router.post(
            f"/deployments/name/{d.flow_name}/{d.name}/schedule_flow_run"
        ).pass_through()
        flow_polls = router.request(
            "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
        ).mock(side_effect=poll_responses)

        assert run_deployment(f"{d.flow_name}/{d.name}", max_polls=3, poll_interval=0)
        assert len(flow_polls.calls) == 3


