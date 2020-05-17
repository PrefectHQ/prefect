import os
import tempfile

import cloudpickle

from distributed.deploy import Cluster

from prefect.environments.execution import DaskCloudProviderEnvironment

from dask_cloudprovider import FargateCluster


def test_create_environment():
    environment = DaskCloudProviderEnvironment(Cluster)
    assert environment


def test_create_dask_cloud_provider_environment():
    environment = DaskCloudProviderEnvironment(provider_class=FargateCluster)
    assert environment
    assert environment.executor_kwargs == {"address": ""}
    assert environment.labels == set()
    assert environment._on_execute is None
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.logger.name == "prefect.DaskCloudProviderEnvironment"


def test_create_dask_cloud_provider_environment_with_executor_kwargs():
    environment = DaskCloudProviderEnvironment(
        provider_class=FargateCluster, executor_kwargs={"test": "here"}
    )
    assert environment
    assert environment.executor_kwargs == {"address": "", "test": "here"}


def test_create_dask_cloud_provider_environment_labels():
    environment = DaskCloudProviderEnvironment(
        provider_class=FargateCluster, labels=["foo"]
    )
    assert environment
    assert environment.labels == set(["foo"])


def test_create_dask_cloud_provider_environment_callbacks():
    def f():
        pass

    environment = DaskCloudProviderEnvironment(
        provider_class=FargateCluster,
        labels=["foo"],
        on_execute=f,
        on_start=f,
        on_exit=f,
    )
    assert environment
    assert environment.labels == set(["foo"])
    assert environment._on_execute is f
    assert environment.on_start is f
    assert environment.on_exit is f


def test_dask_cloud_provider_environment_dependencies():
    environment = DaskCloudProviderEnvironment(provider_class=FargateCluster)
    assert environment.dependencies == ["dask_cloudprovider"]


def test_create_dask_cloud_provider_environment_aws_creds_provided():
    environment = DaskCloudProviderEnvironment(
        provider_class=FargateCluster,
        labels=["foo"],
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        region_name="region",
    )
    assert environment
    assert environment.labels == set(["foo"])
    assert environment._provider_kwargs["aws_access_key_id"] == "id"
    assert environment._provider_kwargs["aws_secret_access_key"] == "secret"
    assert environment._provider_kwargs["aws_session_token"] == "session"
    assert environment._provider_kwargs["region_name"] == "region"


def test_roundtrip_cloudpickle():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = DaskCloudProviderEnvironment(
            provider_class=FargateCluster, cluster="test", skip_cleanup=False,
        )

        assert environment._provider_kwargs == {
            "cluster": "test",
            "skip_cleanup": False,
        }

        new = cloudpickle.loads(cloudpickle.dumps(environment))
        assert isinstance(new, DaskCloudProviderEnvironment)
        assert new._provider_kwargs == {"cluster": "test", "skip_cleanup": False}
