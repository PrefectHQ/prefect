import asyncio
import uuid
from typing import Dict, List, Tuple, Union
from unittest.mock import MagicMock, Mock

import dateutil.parser
import pytest
from anyio.abc import TaskStatus
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.client.schemas import FlowRun
from prefect.exceptions import InfrastructureNotFound
from prefect.infrastructure.container import DockerRegistry
from prefect.server.schemas.core import Flow
from prefect.settings import get_current_settings
from prefect.testing.utilities import AsyncMock
from prefect.utilities.dockerutils import get_prefect_image_name

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import SecretStr
else:
    from pydantic import SecretStr

import prefect_azure.container_instance
from prefect_azure import AzureContainerInstanceCredentials
from prefect_azure.container_instance import ACRManagedIdentity
from prefect_azure.workers.container_instance import (
    AzureContainerJobConfiguration,
    AzureContainerVariables,  # noqa
    AzureContainerWorker,
    AzureContainerWorkerResult,
    ContainerGroupProvisioningState,
    ContainerRunState,
)


# Helper functions
def credential_values(
    credentials: AzureContainerInstanceCredentials,
) -> Tuple[str, str, str]:
    """
    Helper function to extract values from an Azure container instances
    credential block

    Args:
        credentials: The credential to extract values from

    Returns:
        A tuple containing (client_id, client_secret, tenant_id) from
        the credentials block
    """
    return (
        credentials.client_id,
        credentials.client_secret.get_secret_value(),
        credentials.tenant_id,
    )


def create_mock_container_group(state: str, exit_code: Union[int, None]):
    """
    Creates a mock container group with a single container to serve as a stand-in for
    an Azure ContainerInstanceManagementClient's container_group property.

    Args:
        state: The state the single container in the group should report.
        exit_code: The container's exit code, or None

    Returns:
        A mock container group.
    """
    container_group = Mock()
    container = Mock()
    container.instance_view.current_state.state = state
    container.instance_view.current_state.exit_code = exit_code
    containers = [container]
    container_group.containers = containers
    # Azure assigns all provisioned container groups a stringified
    # UUID name.
    container_group.name = str(uuid.uuid4())
    return container_group


async def create_job_configuration(
    aci_credentials, worker_flow_run, overrides={}, run_prep=True
):
    """
    Returns a basic initialized ACI infrastructure block suitable for use
    in a variety of tests.
    """
    values = {
        "command": "test",
        "env": {},
        "aci_credentials": aci_credentials,
        "resource_group_name": "test_group",
        "subscription_id": SecretStr("sub_id"),
        "name": None,
        "task_watch_poll_interval": 0.05,
        "stream_output": False,
    }

    for k, v in overrides.items():
        values = {**values, k: v}

    container_instance_variables = AzureContainerVariables(**values)

    json_config = {
        "job_configuration": AzureContainerJobConfiguration.json_template(),
        "variables": container_instance_variables.dict(),
    }

    container_instance_configuration = (
        await AzureContainerJobConfiguration.from_template_and_values(
            json_config, values
        )
    )

    if run_prep:
        container_instance_configuration.prepare_for_flow_run(worker_flow_run)

    return container_instance_configuration


def get_command_from_deployment_parameters(parameters):
    deployment_arm_template = parameters.template
    # We're only interested in the first resource, because our ACI
    # flow run container groups only have a single container by default.
    deployment_resources = deployment_arm_template["resources"][0]
    deployment_properties = deployment_resources["properties"]
    deployment_containers = deployment_properties["containers"]

    command = deployment_containers[0]["properties"]["command"]
    return command


@pytest.fixture()
def running_worker_container_group():
    """
    A fixture that returns a mock container group simulating a
    a container group that is currently running a flow run.
    """
    container_group = create_mock_container_group(state="Running", exit_code=None)
    container_group.provisioning_state = ContainerGroupProvisioningState.SUCCEEDED
    return container_group


@pytest.fixture()
def completed_worker_container_group():
    """
    A fixture that returns a mock container group simulating a
    a container group that successfully completed its flow run.
    """
    container_group = create_mock_container_group(state="Terminated", exit_code=0)
    container_group.provisioning_state = ContainerGroupProvisioningState.SUCCEEDED

    return container_group


# Fixtures
@pytest.fixture
def aci_credentials(monkeypatch):
    client_id = "test_client_id"
    client_secret = "test_client_secret"
    tenant_id = "test_tenant_id"

    mock_credential = Mock(wraps=ClientSecretCredential, return_value=Mock())

    monkeypatch.setattr(
        prefect_azure.credentials,
        "ClientSecretCredential",
        mock_credential,
    )

    credentials = AzureContainerInstanceCredentials(
        client_id=client_id, client_secret=client_secret, tenant_id=tenant_id
    )

    return credentials


@pytest.fixture
async def aci_worker(mock_prefect_client, monkeypatch):
    return AzureContainerWorker(work_pool_name="test_pool")


@pytest.fixture()
def job_configuration(aci_credentials, worker_flow_run):
    """
    Returns a basic initialized ACI infrastructure block suitable for use
    in a variety of tests.
    """
    return asyncio.run(create_job_configuration(aci_credentials, worker_flow_run))


@pytest.fixture()
async def raw_job_configuration(aci_credentials, worker_flow_run):
    """
    Returns a basic job configuration suitable for use in a variety of tests.
    ``prepare_for_flow_run`` has not called on the returned configuration, so you
    will need to call it yourself before using the job configuration.
    """
    return await create_job_configuration(
        aci_credentials, worker_flow_run, run_prep=False
    )


@pytest.fixture()
def mock_aci_client(monkeypatch, mock_resource_client):
    """
    A fixture that provides a mock Azure Container Instances client
    """
    container_groups = Mock(name="container_group")
    creation_status_poller = Mock(name="created container groups")
    creation_status_poller_result = Mock(name="created container groups result")
    container_groups.begin_create_or_update.side_effect = (
        lambda *args: creation_status_poller
    )
    creation_status_poller.result.side_effect = lambda: creation_status_poller_result
    creation_status_poller_result.provisioning_state = (
        ContainerGroupProvisioningState.SUCCEEDED
    )
    creation_status_poller_result.name = str(uuid.uuid4())
    container = Mock()
    container.instance_view.current_state.exit_code = 0
    container.instance_view.current_state.state = ContainerRunState.TERMINATED
    containers = Mock(name="containers", containers=[container])
    container_groups.get.side_effect = [containers]
    creation_status_poller_result.containers = [containers]

    aci_client = Mock(container_groups=container_groups)
    monkeypatch.setattr(
        prefect_azure.credentials,
        "ContainerInstanceManagementClient",
        Mock(return_value=aci_client),
    )
    return aci_client


@pytest.fixture()
def mock_prefect_client(monkeypatch, worker_flow):
    """
    A fixture that provides a mock Prefect client
    """
    mock_client = Mock()
    mock_client.read_flow = AsyncMock()
    mock_client.read_flow.return_value = worker_flow

    monkeypatch.setattr(
        prefect_azure.workers.container_instance,
        "get_client",
        Mock(return_value=mock_client),
    )

    return mock_client


@pytest.fixture()
def mock_resource_client(monkeypatch):
    mock_resource_client = MagicMock(spec=ResourceManagementClient)

    def return_group(name: str):
        client = ResourceManagementClient
        return client.models().ResourceGroup(name=name, location="useast")

    mock_resource_client.resource_groups.get = Mock(side_effect=return_group)

    monkeypatch.setattr(
        AzureContainerInstanceCredentials,
        "get_resource_client",
        MagicMock(return_value=mock_resource_client),
    )

    return mock_resource_client


@pytest.fixture
def worker_flow():
    return Flow(id=uuid.uuid4(), name="test-flow")


@pytest.fixture
def worker_flow_run(worker_flow):
    return FlowRun(id=uuid.uuid4(), flow_id=worker_flow.id, name="test-flow-run")


# Tests


async def test_worker_valid_command_validation(aci_credentials, worker_flow_run):
    # ensure the validator allows valid commands to pass through
    command = "command arg1 arg2"

    aci_job_config = await create_job_configuration(
        aci_credentials, worker_flow_run, {"command": command}
    )

    assert aci_job_config.command == command


def test_worker_invalid_command_validation(aci_credentials):
    # ensure invalid commands cause a validation error
    with pytest.raises(ValueError):
        AzureContainerJobConfiguration(
            command=["invalid_command", "arg1", "arg2"],  # noqa
            subscription_id=SecretStr("test"),
            resource_group_name="test",
            aci_credentials=aci_credentials,
        )


async def test_worker_container_client_creation(
    worker_flow_run,
    job_configuration,
    aci_credentials,
    monkeypatch,
    mock_prefect_client,
):
    # verify that the Azure Container Instances client and Azure Resource clients
    # are created correctly.

    mock_azure_credential = Mock(spec=ClientSecretCredential)
    monkeypatch.setattr(
        prefect_azure.credentials,
        "ClientSecretCredential",
        Mock(return_value=mock_azure_credential),
    )

    # don't use the mock_aci_client or mock_resource_client_fixtures, because we want to
    # test the call to the client constructors to ensure the block is calling them
    # with the correct information.
    mock_container_client_constructor = Mock()
    monkeypatch.setattr(
        prefect_azure.credentials,
        "ContainerInstanceManagementClient",
        mock_container_client_constructor,
    )

    mock_resource_client_constructor = Mock()
    monkeypatch.setattr(
        prefect_azure.credentials,
        "ResourceManagementClient",
        mock_resource_client_constructor,
    )

    subscription_id = "test_subscription"
    job_configuration.subscription_id = SecretStr(value=subscription_id)

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        # Using mock Azure clients to avoid making real calls to Azure
        # during testing means that the client will raise an exception
        # unless we mock multiple client responses. Since we're only
        # mocking what's needed for this test, we expect the worker to
        # raise an exception when it tries to proceed further.
        with pytest.raises(RuntimeError):
            await aci_worker.run(worker_flow_run, job_configuration)

    mock_resource_client_constructor.assert_called_once_with(
        credential=mock_azure_credential,
        subscription_id=subscription_id,
    )
    mock_container_client_constructor.assert_called_once_with(
        credential=mock_azure_credential,
        subscription_id=subscription_id,
    )


@pytest.mark.usefixtures("mock_aci_client")
async def test_worker_credentials_are_used(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    aci_credentials,
    mock_aci_client,
    mock_resource_client,
    monkeypatch,
):
    (client_id, client_secret, tenant_id) = credential_values(aci_credentials)

    mock_client_secret = Mock(name="Mock client secret", return_value=client_secret)
    mock_credential = Mock(wraps=ClientSecretCredential, return_value=Mock())

    monkeypatch.setattr(
        aci_credentials.client_secret, "get_secret_value", mock_client_secret
    )
    monkeypatch.setattr(
        prefect_azure.credentials, "ClientSecretCredential", mock_credential
    )

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        # Using mock Azure clients to avoid making real calls to Azure
        # during testing means that the client will raise an exception
        # unless we mock multiple client responses. Since we're only
        # mocking what's needed for this test, we expect the worker to
        # raise an exception when it tries to proceed further.
        with pytest.raises(RuntimeError):
            await aci_worker.run(worker_flow_run, job_configuration)

    mock_client_secret.assert_called_once()
    mock_credential.assert_called_once_with(
        client_id=client_id, client_secret=client_secret, tenant_id=tenant_id
    )


async def test_aci_worker_deployment_call(
    mock_prefect_client,
    mock_aci_client,
    mock_resource_client,
    completed_worker_container_group,
    worker_flow_run,
    job_configuration,
    monkeypatch,
):
    # simulate a successful deployment of a container group to Azure
    completed_worker_container_group.provisioning_state = (
        ContainerGroupProvisioningState.SUCCEEDED
    )

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        monkeypatch.setattr(
            aci_worker,
            "_get_container_group",
            Mock(return_value=completed_worker_container_group),
        )
        mock_poller = Mock()
        # the deployment poller should return a successful deployment
        mock_poller.done = Mock(return_value=True)
        mock_poller_result = MagicMock()
        mock_poller_result.properties.provisioning_state = (
            ContainerGroupProvisioningState.SUCCEEDED
        )
        mock_poller.result = Mock(return_value=mock_poller_result)

        mock_resource_client.deployments.begin_create_or_update = Mock(
            return_value=mock_poller
        )

        # ensure the worker always tries to call the Azure deployments SDK
        # to create the container
        await aci_worker.run(worker_flow_run, job_configuration)

    mock_resource_client.deployments.begin_create_or_update.assert_called_once()


@pytest.mark.parametrize(
    "entrypoint, job_command, expected_template_command",
    [
        # If no entrypoint is provided, just use the command
        (None, "command arg1 arg2", ["command", "arg1", "arg2"]),
        # entrypoint and command should be combined if both are provided
        (
            "/test/entrypoint.sh",
            "command arg1 arg2",
            ["/test/entrypoint.sh", "command", "arg1", "arg2"],
        ),
    ],
)
async def test_worker_uses_entrypoint_correctly_in_template(
    mock_prefect_client,
    aci_credentials,
    worker_flow_run,
    mock_aci_client,
    mock_resource_client,
    monkeypatch,
    entrypoint,
    job_command,
    expected_template_command,
):
    mock_deployment_call = Mock()
    mock_resource_client.deployments.begin_create_or_update = mock_deployment_call

    job_overrides = {
        "entrypoint": entrypoint,
        "command": job_command,
    }

    run_job_configuration = await create_job_configuration(
        aci_credentials, worker_flow_run, job_overrides
    )

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        # We haven't mocked out the container group creation, so this should fail
        # and that's expected. We just want to ensure the entrypoint is used correctly.
        with pytest.raises(RuntimeError):
            await aci_worker.run(worker_flow_run, run_job_configuration)

    mock_deployment_call.assert_called_once()
    (_, kwargs) = mock_deployment_call.call_args

    deployment_parameters = kwargs.get("parameters").properties
    called_command = get_command_from_deployment_parameters(deployment_parameters)
    assert called_command == expected_template_command


async def test_delete_after_group_creation_failure(
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    monkeypatch,
    mock_prefect_client,
):
    # if provisioning failed, the container group should be deleted
    mock_container_group = Mock()
    mock_container_group.provisioning_state.return_value = (
        ContainerGroupProvisioningState.FAILED
    )

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        monkeypatch.setattr(
            aci_worker, "_wait_for_task_container_start", mock_container_group
        )

        # We expect the worker to raise an exception when creating the container group
        # fails. We also expect the `finally` block to be called and the container group
        # to be deleted.
        with pytest.raises(RuntimeError):
            await aci_worker.run(worker_flow_run, configuration=job_configuration)

    mock_aci_client.container_groups.begin_delete.assert_called_once()


async def test_delete_after_group_creation_success(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    monkeypatch,
    running_worker_container_group,
):
    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        # if provisioning was successful, the container group should
        # eventually be deleted
        monkeypatch.setattr(
            aci_worker,
            "_wait_for_task_container_start",
            Mock(return_value=running_worker_container_group),
        )

        await aci_worker.run(worker_flow_run, job_configuration)

    mock_aci_client.container_groups.begin_delete.assert_called_once()


async def test_delete_after_after_exception(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    mock_resource_client,
    monkeypatch,
):
    # If an exception was thrown while waiting for container group provisioning,
    # we should still attempt to delete the container group. This is to ensure
    # that we don't leave orphaned container groups in the event of an error.
    mock_resource_client.deployments.begin_create_or_update.side_effect = (
        HttpResponseError(message="it broke")
    )

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        with pytest.raises(HttpResponseError):
            await aci_worker.run(worker_flow_run, job_configuration)

    mock_aci_client.container_groups.begin_delete.assert_called_once()


@pytest.mark.usefixtures("mock_aci_client")
async def test_task_status_started_on_provisioning_success(
    worker_flow_run,
    job_configuration,
    running_worker_container_group,
    mock_prefect_client,
    monkeypatch,
):
    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        monkeypatch.setattr(
            aci_worker, "_provisioning_succeeded", Mock(return_value=True)
        )

        monkeypatch.setattr(
            aci_worker,
            "_wait_for_task_container_start",
            Mock(return_value=running_worker_container_group),
        )

        task_status = Mock(spec=TaskStatus)

        await aci_worker.run(
            worker_flow_run, job_configuration, task_status=task_status
        )

    flow = await mock_prefect_client.read_flow(worker_flow_run.flow_id)

    container_group_name = f"{flow.name}-{worker_flow_run.id}"

    identifier = f"{worker_flow_run.id}:{container_group_name}"

    task_status.started.assert_called_once_with(value=identifier)


@pytest.mark.usefixtures("mock_aci_client")
async def test_task_status_not_started_on_provisioning_failure(
    worker_flow_run, job_configuration, monkeypatch, mock_prefect_client
):
    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        monkeypatch.setattr(
            aci_worker, "_provisioning_succeeded", Mock(return_value=False)
        )

        task_status = Mock(spec=TaskStatus)

        # we expect the worker to raise an exception if provisioning fails
        with pytest.raises(RuntimeError, match="Container creation failed"):
            await aci_worker.run(worker_flow_run, job_configuration, task_status)

    task_status.started.assert_not_called()


async def test_provisioning_timeout_throws_exception(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    mock_resource_client,
):
    mock_poller = Mock()
    mock_poller.done.return_value = False
    mock_resource_client.deployments.begin_create_or_update.side_effect = (
        lambda *args, **kwargs: mock_poller
    )

    # avoid delaying test runs
    job_configuration.task_watch_poll_interval = 0.09
    job_configuration.task_start_timeout_seconds = 0.10

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        # ensure that the worker throws an exception if the container group
        # provisioning times out
        with pytest.raises(RuntimeError, match="Timed out after"):
            await aci_worker.run(worker_flow_run, job_configuration)


async def test_watch_for_container_termination(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    mock_resource_client,
    monkeypatch,
    running_worker_container_group,
    completed_worker_container_group,
):
    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        monkeypatch.setattr(
            aci_worker, "_provisioning_succeeded", Mock(return_value=True)
        )

        monkeypatch.setattr(
            aci_worker,
            "_wait_for_task_container_start",
            Mock(return_value=running_worker_container_group),
        )

        # make the worker wait a few times before we give it a successful result
        # so we can make sure the watcher actually watches instead of skipping
        # the timeout
        run_count = 0

        def get_container_group(**kwargs):
            nonlocal run_count
            run_count += 1
            if run_count < 5:
                return running_worker_container_group
            else:
                return completed_worker_container_group

        mock_aci_client.container_groups.get.side_effect = get_container_group

        job_configuration.task_watch_poll_interval = 0.02

        result = await aci_worker.run(worker_flow_run, job_configuration)

    # ensure the watcher was watching
    assert run_count == 5
    assert mock_aci_client.container_groups.get.call_count == run_count
    # ensure the run completed
    assert isinstance(result, AzureContainerWorkerResult)


async def test_quick_termination_handling(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    completed_worker_container_group,
    monkeypatch,
):
    # ensure that everything works as expected in the case where the container has
    # already finished its flow run by the time the poller picked up the container
    # group's successful provisioning status.

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        monkeypatch.setattr(
            aci_worker, "_provisioning_succeeded", Mock(return_value=True)
        )

        monkeypatch.setattr(
            aci_worker,
            "_wait_for_task_container_start",
            Mock(return_value=completed_worker_container_group),
        )

        result = await aci_worker.run(worker_flow_run, job_configuration)

    # ensure the watcher didn't need to call to check status since the run
    # already completed.
    mock_aci_client.container_groups.get.assert_not_called()
    # ensure the run completed
    assert isinstance(result, AzureContainerWorkerResult)


async def test_output_streaming(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    running_worker_container_group,
    completed_worker_container_group,
    monkeypatch,
):
    # override datetime.now to ensure run start time is before log line timestamps
    run_start_time = dateutil.parser.parse("2022-10-03T20:40:05.3119525Z")
    mock_datetime = Mock()
    mock_datetime.datetime.now.return_value = run_start_time

    monkeypatch.setattr(
        prefect_azure.workers.container_instance, "datetime", mock_datetime
    )

    log_lines = """
2022-10-03T20:41:05.3119525Z 20:41:05.307 | INFO    | Flow run 'ultramarine-dugong' - Created task run "Test-39fdf8ff-0" for task "ACI Test"
2022-10-03T20:41:05.3120697Z 20:41:05.308 | INFO    | Flow run 'ultramarine-dugong' - Executing "Test-39fdf8ff-0" immediately...
2022-10-03T20:41:05.6215928Z 20:41:05.616 | INFO    | Task run "Test-39fdf8ff-0" - Test Message
2022-10-03T20:41:05.7758864Z 20:41:05.775 | INFO    | Task run "Test-39fdf8ff-0" - Finished in state Completed()
"""  # noqa

    # include some overlap in the second batch so we can make sure output
    # is not duplicated
    next_log_lines = """
2022-10-03T20:41:05.6215928Z 20:41:05.616 | INFO    | Task run "Test-39fdf8ff-0" - Test Message
2022-10-03T20:41:05.7758864Z 20:41:05.775 | INFO    | Task run "Test-39fdf8ff-0" - Finished in state Completed()
2022-10-03T20:41:13.0149593Z 20:41:13.012 | INFO    | Flow run 'ultramarine-dugong' - Created task run "Test-39fdf8ff-1" for task "ACI Test"
2022-10-03T20:41:13.0152433Z 20:41:13.013 | INFO    | Flow run 'ultramarine-dugong' - Executing "Test-39fdf8ff-1" immediately...
2022-broken-03T20:41:13.0152433Z 20:41:13.013 | INFO    | Log line with broken timestamp should not be printed
    """  # noqa

    log_count = 0

    def get_logs(*args, **kwargs):
        nonlocal log_count
        logs = Mock()
        if log_count == 0:
            log_count += 1
            logs.content = log_lines
        elif log_count == 1:
            log_count += 1
            logs.content = next_log_lines
        else:
            logs.content = ""

        return logs

    run_count = 0

    def get_container_group(**kwargs):
        nonlocal run_count
        run_count += 1
        if run_count < 4:
            return running_worker_container_group
        else:
            return completed_worker_container_group

    mock_aci_client.container_groups.get.side_effect = get_container_group

    mock_log_call = Mock(side_effect=get_logs)
    monkeypatch.setattr(mock_aci_client.containers, "list_logs", mock_log_call)

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        mock_write_call = Mock(wraps=aci_worker._write_output_line)
        monkeypatch.setattr(aci_worker, "_write_output_line", mock_write_call)

        monkeypatch.setattr(
            aci_worker, "_provisioning_succeeded", Mock(return_value=True)
        )

        monkeypatch.setattr(
            aci_worker,
            "_wait_for_task_container_start",
            Mock(return_value=running_worker_container_group),
        )

        job_configuration.stream_output = True
        job_configuration.name = "streaming test"
        job_configuration.task_watch_poll_interval = 0.02

        await aci_worker.run(worker_flow_run, job_configuration)

    # 6 lines should be written because of the nine test log lines, two overlap
    # and should not be written twice, and one has a broken timestamp so should
    # not be written
    assert mock_write_call.call_count == 6


def test_block_accessible_in_module_toplevel():
    # will raise an exception and fail the test if `AzureContainerInstanceJob`
    # is not accessible directly from `prefect_azure`
    from prefect_azure import AzureContainerWorker  # noqa


def test_secure_environment_variables(
    raw_job_configuration, worker_flow_run, monkeypatch
):
    config = raw_job_configuration
    # setup environment containing an API key we want to keep secret
    base_env: Dict[str, str] = get_current_settings().to_environment_variables(
        exclude_unset=True
    )
    base_env["PREFECT_API_KEY"] = "my-api-key"

    # base_env_call = Mock(return_value=base_env)
    # monkeypatch.setattr(raw_job_configuration, "_base_environment", base_env_call)
    config.env = base_env
    config.prepare_for_flow_run(worker_flow_run)

    container_group = config.arm_template["resources"][0]
    container = container_group["properties"]["containers"][0]

    # get the container's environment variables
    container_env = container["properties"]["environmentVariables"]

    api_key_aci_env_variable: List[Dict] = list(
        filter(lambda v: v["name"] == "PREFECT_API_KEY", container_env)
    )

    # ensure the env variable made it into the list of env variables set in the
    # ACI container
    assert len(api_key_aci_env_variable) == 1
    api_key_entry = api_key_aci_env_variable[0]

    expected = {
        "name": "PREFECT_API_KEY",
        "secureValue": "my-api-key",
    }

    assert api_key_entry == expected


def test_add_docker_registry_credentials(
    raw_job_configuration, worker_flow_run, mock_aci_client, monkeypatch
):
    registry = DockerRegistry(
        username="username",
        password="password",
        registry_url="https://myregistry.dockerhub.com",
    )

    raw_job_configuration.image_registry = registry
    raw_job_configuration.prepare_for_flow_run(worker_flow_run)

    container_group = raw_job_configuration.arm_template["resources"][0]
    image_registry_credentials = container_group["properties"][
        "imageRegistryCredentials"
    ]

    assert len(image_registry_credentials) == 1
    assert image_registry_credentials[0]["server"] == registry.registry_url
    assert image_registry_credentials[0]["username"] == registry.username
    assert (
        image_registry_credentials[0]["password"]
        == registry.password.get_secret_value()
    )


def test_add_acr_registry_identity(
    raw_job_configuration, worker_flow_run, mock_aci_client, monkeypatch
):
    registry = ACRManagedIdentity(
        registry_url="https://myregistry.azurecr.io",
        identity="my-identity",
    )

    raw_job_configuration.image_registry = registry
    raw_job_configuration.prepare_for_flow_run(worker_flow_run)

    container_group = raw_job_configuration.arm_template["resources"][0]
    image_registry_credentials = container_group["properties"][
        "imageRegistryCredentials"
    ]

    assert len(image_registry_credentials) == 1
    assert image_registry_credentials[0]["server"] == registry.registry_url
    assert image_registry_credentials[0]["identity"] == registry.identity


async def test_provisioning_container_group(
    mock_prefect_client,
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    mock_resource_client,
    running_worker_container_group,
    monkeypatch,
):
    mock_deployments = Mock(name="deployments")
    mock_provisioning_call = Mock(
        name="provisioning_call", return_value=running_worker_container_group
    )
    mock_deployments.begin_create_or_update = mock_provisioning_call

    monkeypatch.setattr(mock_resource_client, "deployments", mock_deployments)

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        # We want to ensure that the provisioning call is made; we don't care about
        # the rest of the run, so an exception is expected since we haven't mocked
        # ACI client responses.
        with pytest.raises(RuntimeError):
            await aci_worker.run(worker_flow_run, job_configuration)

    mock_provisioning_call.assert_called_once()


def test_job_configuration_creation():
    config = AzureContainerJobConfiguration(
        resource_group_name="my-resource-group",
        subscription_id="my-subscription-id",
        aci_credentials=AzureContainerInstanceCredentials(
            tenant_id="my-tenant-id",
            client_id="my-client-id",
            client_secret="my-client-secret",
        ),
        arm_template=(
            prefect_azure.workers.container_instance._get_default_arm_template()
        ),
        image="my-image",
        cpu=1,
        memory=1,
        env={"TEST": "VALUE"},
    )

    assert config.image == "my-image"
    assert config.cpu == 1
    assert config.memory == 1
    assert config.env == {"TEST": "VALUE"}
    assert config.resource_group_name == "my-resource-group"
    assert config.subscription_id.get_secret_value() == "my-subscription-id"
    assert config.aci_credentials.tenant_id == "my-tenant-id"
    assert config.aci_credentials.client_id == "my-client-id"
    assert config.aci_credentials.client_secret.get_secret_value() == "my-client-secret"
    assert isinstance(config.arm_template, dict)


async def test_image_populated_in_template_when_not_provided(worker_flow_run):
    config = await AzureContainerJobConfiguration.from_template_and_values(
        base_job_template=AzureContainerWorker.get_default_base_job_template(),
        values=AzureContainerVariables(
            subscription_id="my-subscription-id",
            resource_group_name="my-resource-group",
        ).dict(exclude_unset=True),
    )
    config.prepare_for_flow_run(worker_flow_run)

    assert config.image == get_prefect_image_name()
    assert (
        config.arm_template["resources"][0]["properties"]["containers"][0][
            "properties"
        ]["image"]
        == get_prefect_image_name()
    )


async def test_add_identities(
    raw_job_configuration, worker_flow_run, mock_aci_client, monkeypatch
):
    raw_job_configuration.identities = ["identity1", "identity2", "identity3"]
    raw_job_configuration.prepare_for_flow_run(worker_flow_run)

    container_group = raw_job_configuration.arm_template["resources"][0]
    identities = container_group["identity"]["userAssignedIdentities"]
    assert len(identities) == 3
    # each of the identities in the input list should be the key of one of the
    # entries in the identities dict. The value of each entry doesn't matter as
    # long as it's not null
    for identity in raw_job_configuration.identities:
        assert identities[identity] is not None


async def test_add_subnet_ids(
    raw_job_configuration, worker_flow_run, mock_aci_client, monkeypatch
):
    raw_job_configuration.subnet_ids = ["subnet1", "subnet2", "subnet3"]
    raw_job_configuration.prepare_for_flow_run(worker_flow_run)

    container_group = raw_job_configuration.arm_template["resources"][0]
    subnet_ids = container_group["properties"]["subnetIds"]
    assert len(subnet_ids) == 3
    # each of the subnet ids in the input list should be the value of one of the
    # entries in the subnet ids list
    for subnet_id in raw_job_configuration.subnet_ids:
        assert {"id": subnet_id} in subnet_ids


async def test_add_dns_servers(
    raw_job_configuration, worker_flow_run, mock_aci_client, monkeypatch
):
    raw_job_configuration.dns_servers = ["dns1", "dns2", "dns3"]
    raw_job_configuration.prepare_for_flow_run(worker_flow_run)

    container_group = raw_job_configuration.arm_template["resources"][0]
    dns_config = container_group["properties"]["dnsConfig"]
    assert len(dns_config["nameServers"]) == 3
    # each of the dns servers in the input list should be the value of one of the
    # entries in the dns servers list
    for dns_server in raw_job_configuration.dns_servers:
        assert dns_server in dns_config["nameServers"]


async def test_kill_infrastructure_deletes_running_container_group(
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    mock_prefect_client,
    monkeypatch,
    running_worker_container_group,
):
    mock_container_groups = Mock(name="container_groups")
    mock_delete_status_poller = Mock(name="delete_status_poller")
    mock_delete_status_poller.done = Mock(return_value=True)
    mock_deletion_call = Mock(
        name="deletion_call", return_value=mock_delete_status_poller
    )
    mock_aci_client.container_groups = mock_container_groups
    mock_container_groups.begin_delete = mock_deletion_call

    flow = await mock_prefect_client.read_flow(worker_flow_run.flow_id)
    container_group_name = f"{flow.name}-{worker_flow_run.id}"
    identifier = f"{worker_flow_run.id}:{container_group_name}"

    mock_container_group_get = Mock(return_value=running_worker_container_group)
    mock_aci_client.container_groups.get = mock_container_group_get

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        await aci_worker.kill_infrastructure(identifier, job_configuration)

    # Kill_infrastructure should check if the container group exists before
    # attempting to delete it
    mock_container_group_get.assert_called_once_with(
        resource_group_name=job_configuration.resource_group_name,
        container_group_name=container_group_name,
    )

    # Kill_infrastructure should delete the container group if it exists
    mock_deletion_call.assert_called_once_with(
        resource_group_name=job_configuration.resource_group_name,
        container_group_name=container_group_name,
    )

    # Also ensure that the deletion times out if Azure does not delete
    # the container group quickly enough.
    mock_delete_status_poller.done.return_value = False
    monkeypatch.setattr(
        prefect_azure.workers.container_instance,
        "CONTAINER_GROUP_DELETION_TIMEOUT_SECONDS",
        0.03,
    )
    job_configuration.task_watch_poll_interval = 0.01

    async with aci_worker:
        # Deletion timing out should raise a RuntimeError
        with pytest.raises(RuntimeError):
            await aci_worker.kill_infrastructure(identifier, job_configuration)


async def test_kill_infrastructure_raises_exception_if_container_group_missing(
    worker_flow_run,
    job_configuration,
    mock_aci_client,
    mock_prefect_client,
):
    mock_container_groups = Mock(name="container_groups")
    mock_aci_client.container_groups = mock_container_groups
    mock_container_groups.get = Mock(side_effect=ResourceNotFoundError())

    mock_deletion_call = Mock(name="deletion_call", return_value=None)
    mock_container_groups.begin_delete = mock_deletion_call

    flow = await mock_prefect_client.read_flow(worker_flow_run.flow_id)
    container_group_name = f"{flow.name}-{worker_flow_run.id}"
    identifier = f"{worker_flow_run.id}:{container_group_name}"

    async with AzureContainerWorker(work_pool_name="test_pool") as aci_worker:
        with pytest.raises(InfrastructureNotFound):
            await aci_worker.kill_infrastructure(identifier, job_configuration)

    # Kill_infrastructure should check if the container group exists before
    # attempting to delete it
    mock_container_groups.get.assert_called_once_with(
        resource_group_name=job_configuration.resource_group_name,
        container_group_name=container_group_name,
    )

    # Kill_infrastructure should not attempt to delete the container group if it
    # does not exist
    mock_deletion_call.assert_not_called()
