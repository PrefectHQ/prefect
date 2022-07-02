import sys
from typing import NamedTuple

import pytest

import prefect
from prefect.orion.schemas.data import DataDocument


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int


def fake_python_version(
    major=sys.version_info.major,
    minor=sys.version_info.minor,
    micro=sys.version_info.micro,
    releaselevel=sys.version_info.releaselevel,
    serial=sys.version_info.serial,
):
    return VersionInfo(major, minor, micro, releaselevel, serial)


@pytest.fixture
async def python_executable_test_deployment(orion_client):
    """
    A deployment for a flow that returns the current python executable path for
    testing that flows are run with the correct python version
    """

    @prefect.flow
    def my_flow():
        import sys

        return sys.executable

    flow_id = await orion_client.create_flow(my_flow)

    flow_data = DataDocument.encode("cloudpickle", my_flow)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="python_executable_test_deployment",
        flow_data=flow_data,
    )

    return deployment_id


@pytest.fixture
async def os_environ_test_deployment(orion_client):
    """
    A deployment for a flow that returns the current environment variables for testing
    that flows are run with environment variables populated.
    """

    @prefect.flow
    def my_flow():
        import os

        return os.environ

    flow_id = await orion_client.create_flow(my_flow)

    flow_data = DataDocument.encode("cloudpickle", my_flow)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="os_environ_test_deployment",
        flow_data=flow_data,
    )

    return deployment_id


@pytest.fixture
async def prefect_settings_test_deployment(orion_client):
    """
    A deployment for a flow that returns the current Prefect settings object.
    """

    @prefect.flow
    def my_flow():
        import prefect.settings

        return prefect.settings.get_current_settings()

    flow_id = await orion_client.create_flow(my_flow)

    flow_data = DataDocument.encode("cloudpickle", my_flow)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="prefect_settings_test_deployment",
        flow_data=flow_data,
    )

    return deployment_id
