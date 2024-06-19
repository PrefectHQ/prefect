import os
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

import docker
import docker.errors
import docker.models.containers
import docker.models.images
import pendulum
import pytest
from prefect_docker.deployments.steps import (
    build_docker_image,
    push_docker_image,
)

import prefect
import prefect.utilities.dockerutils

FAKE_CONTAINER_ID = "fake-id"
FAKE_BASE_URL = "my-url"
FAKE_DEFAULT_TAG = "2022-08-31t18-01-32-00-00"
FAKE_IMAGE_NAME = "registry/repo"
FAKE_TAG = "mytag"
FAKE_ADDITIONAL_TAGS = ["addtag1", "addtag2"]
FAKE_EVENT = [{"status": "status", "progress": "progress"}, {"status": "status"}]
FAKE_CREDENTIALS = {
    "username": "user",
    "password": "pass",
    "registry_url": "https://registry.com",
    "reauth": True,
}


@pytest.fixture(autouse=True)
def reset_cachable_steps(monkeypatch):
    monkeypatch.setattr("prefect_docker.deployments.steps.STEP_OUTPUT_CACHE", {})


@pytest.fixture
def mock_docker_client(monkeypatch):
    mock_client = MagicMock(name="DockerClient", spec=docker.DockerClient)
    mock_client.version.return_value = {"Version": "20.10"}

    # Build a fake container object to return
    fake_container = docker.models.containers.Container()
    fake_container.client = MagicMock(name="Container.client")
    fake_container.collection = MagicMock(name="Container.collection")
    attrs = {
        "Id": FAKE_CONTAINER_ID,
        "Name": "fake-name",
        "State": {
            "Status": "exited",
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": True,
            "Pid": 0,
            "ExitCode": 0,
            "Error": "",
            "StartedAt": "2022-08-31T18:01:32.645851548Z",
            "FinishedAt": "2022-08-31T18:01:32.657076632Z",
        },
    }
    fake_container.collection.get().attrs = attrs
    fake_container.attrs = attrs
    fake_container.stop = MagicMock()
    # Return the fake container on lookups and creation
    mock_client.containers.get.return_value = fake_container
    mock_client.containers.create.return_value = fake_container

    # Set attributes for infrastructure PID lookup
    fake_api = MagicMock(name="APIClient")
    fake_api.build.return_value = [
        {"aux": {"ID": FAKE_CONTAINER_ID}},
    ]
    fake_api.base_url = FAKE_BASE_URL
    mock_client.api = fake_api

    mock_docker_client_func = MagicMock(
        name="docker_client", spec=prefect.utilities.dockerutils.docker_client
    )
    mock_docker_client_func.return_value.__enter__.return_value = mock_client
    monkeypatch.setattr(
        "prefect_docker.deployments.steps.docker_client", mock_docker_client_func
    )
    return mock_client


@pytest.fixture
def mock_pendulum(monkeypatch):
    mock_pendulum = MagicMock(name="pendulum", spec=pendulum)
    mock_pendulum.now.return_value = pendulum.datetime(2022, 8, 31, 18, 1, 32)
    monkeypatch.setattr("prefect_docker.deployments.steps.pendulum", mock_pendulum)
    return mock_pendulum


@pytest.mark.parametrize(
    "kwargs, expected_image",
    [
        ({"image_name": "registry/repo"}, f"registry/repo:{FAKE_DEFAULT_TAG}"),
        (
            {
                "image_name": "registry/repo",
                "dockerfile": "Dockerfile.dev",
            },
            f"registry/repo:{FAKE_DEFAULT_TAG}",
        ),
        (
            {"image_name": "registry/repo", "tag": "mytag"},
            "registry/repo:mytag",
        ),
        (
            {
                "image_name": "registry/repo",
            },
            f"registry/repo:{FAKE_DEFAULT_TAG}",
        ),
        (
            {"image_name": "registry/repo", "dockerfile": "auto"},
            f"registry/repo:{FAKE_DEFAULT_TAG}",
        ),
        (
            {
                "image_name": "registry/repo",
                "dockerfile": "auto",
            },
            f"registry/repo:{FAKE_DEFAULT_TAG}",
        ),
        (
            {
                "image_name": "registry/repo",
                "dockerfile": "auto",
                "path": "path/to/context",
            },
            f"registry/repo:{FAKE_DEFAULT_TAG}",
        ),
        (
            {
                "image_name": "registry/repo",
                "tag": "mytag",
                "additional_tags": FAKE_ADDITIONAL_TAGS,
            },
            "registry/repo:mytag",
        ),
    ],
)
def test_build_docker_image(
    monkeypatch,
    mock_docker_client,
    mock_pendulum,
    kwargs,
    expected_image,
):
    auto_build = False
    image_name = kwargs.get("image_name")
    dockerfile = kwargs.get("dockerfile", "Dockerfile")
    tag = kwargs.get("tag", FAKE_DEFAULT_TAG)
    additional_tags = kwargs.get("additional_tags", None)
    path = kwargs.get("path", os.getcwd())
    result = build_docker_image(
        **kwargs | {"ignore_cache": True}
    )  # ignore_cache=True to avoid caching here

    assert result["image"] == expected_image
    assert result["tag"] == tag
    assert result["image_name"] == image_name
    assert result["image_id"] == FAKE_CONTAINER_ID

    if additional_tags:
        assert result["additional_tags"] == FAKE_ADDITIONAL_TAGS
        mock_docker_client.images.get.return_value.tag.assert_has_calls(
            [
                mock.call(repository=image_name, tag=tag),
                mock.call(repository=image_name, tag=FAKE_ADDITIONAL_TAGS[0]),
                mock.call(repository=image_name, tag=FAKE_ADDITIONAL_TAGS[1]),
            ]
        )
    else:
        assert result["additional_tags"] == []
        mock_docker_client.images.get.return_value.tag.assert_called_once_with(
            repository=image_name, tag=tag
        )

    if dockerfile == "auto":
        auto_build = True
        dockerfile = "Dockerfile"

    mock_docker_client.api.build.assert_called_once_with(
        path=path,
        dockerfile=dockerfile,
        decode=True,
        pull=True,
        labels=prefect.utilities.dockerutils.IMAGE_LABELS,
    )

    mock_docker_client.images.get.assert_called_once_with(FAKE_CONTAINER_ID)

    if auto_build:
        assert not Path("Dockerfile").exists()


def test_build_docker_image_raises_with_auto_and_existing_dockerfile():
    try:
        Path("Dockerfile").touch()
        with pytest.raises(ValueError, match="Dockerfile already exists"):
            build_docker_image(
                image_name="registry/repo", dockerfile="auto", ignore_cache=True
            )
    finally:
        Path("Dockerfile").unlink()


def test_real_auto_dockerfile_build(docker_client_with_cleanup):
    os.chdir(str(Path(__file__).parent.parent / "test-project"))
    image_name = "local/repo"
    tag = f"test-{uuid4()}"
    image_reference = f"{image_name}:{tag}"
    try:
        result = build_docker_image(
            image_name=image_name, tag=tag, dockerfile="auto", pull=False
        )
        image: docker.models.images.Image = docker_client_with_cleanup.images.get(
            result["image"]
        )
        assert image

        expected_prefect_version = prefect.__version__
        expected_prefect_version = expected_prefect_version.replace(".dirty", "")
        expected_prefect_version = expected_prefect_version.split("+")[0]

        cases = [
            {"command": "prefect version", "expected": expected_prefect_version},
            {"command": "ls", "expected": "requirements.txt"},
        ]

        for case in cases:
            output = docker_client_with_cleanup.containers.run(
                image=result["image"],
                command=case["command"],
                labels=["prefect-docker-test"],
                remove=True,
            )
            assert case["expected"] in output.decode()

        output = docker_client_with_cleanup.containers.run(
            image=result["image"],
            command="python -c 'import pandas; print(pandas.__version__)'",
            labels=["prefect-docker-test"],
            remove=True,
        )
        assert "2" in output.decode()

    finally:
        docker_client_with_cleanup.containers.prune(
            filters={"label": "prefect-docker-test"}
        )
        try:
            docker_client_with_cleanup.images.remove(image=image_reference, force=True)
        except docker.errors.ImageNotFound:
            pass


def test_push_docker_image_with_additional_tags(mock_docker_client, monkeypatch):
    # Mock stdout
    mock_stdout = MagicMock()
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    # client.api.push can return a generator or strings; here we test with a generator
    # we end up calling client.api.push 3 times in this test (once for tag, twice for
    # additional_tags), therefore we need the mocked push to return 3 generators
    mock_docker_client.api.push.side_effect = [
        (e for e in FAKE_EVENT),
        (e for e in FAKE_EVENT),
        (e for e in FAKE_EVENT),
    ]

    result = push_docker_image(
        image_name=FAKE_IMAGE_NAME,
        tag=FAKE_TAG,
        credentials=FAKE_CREDENTIALS,
        additional_tags=FAKE_ADDITIONAL_TAGS,
    )

    assert result["image_name"] == FAKE_IMAGE_NAME
    assert result["tag"] == FAKE_TAG
    assert result["image"] == f"{FAKE_IMAGE_NAME}:{FAKE_TAG}"
    assert result["additional_tags"] == FAKE_ADDITIONAL_TAGS

    mock_docker_client.api.push.assert_has_calls(
        [
            mock.call(
                repository=FAKE_IMAGE_NAME,
                tag=FAKE_TAG,
                stream=True,
                decode=True,
            ),
            mock.call(
                repository=FAKE_IMAGE_NAME,
                tag=FAKE_ADDITIONAL_TAGS[0],
                stream=True,
                decode=True,
            ),
            mock.call(
                repository=FAKE_IMAGE_NAME,
                tag=FAKE_ADDITIONAL_TAGS[1],
                stream=True,
                decode=True,
            ),
        ]
    )
    assert mock_stdout.write.call_count == 15


def test_push_docker_image_with_credentials(mock_docker_client, monkeypatch):
    # Mock stdout
    mock_stdout = MagicMock()
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    mock_docker_client.api.push.return_value = FAKE_EVENT

    result = push_docker_image(
        image_name=FAKE_IMAGE_NAME, tag=FAKE_TAG, credentials=FAKE_CREDENTIALS
    )

    assert result["image_name"] == FAKE_IMAGE_NAME
    assert result["tag"] == FAKE_TAG
    assert result["image"] == f"{FAKE_IMAGE_NAME}:{FAKE_TAG}"

    mock_docker_client.login.assert_called_once_with(
        username=FAKE_CREDENTIALS["username"],
        password=FAKE_CREDENTIALS["password"],
        registry=FAKE_CREDENTIALS["registry_url"],
        reauth=FAKE_CREDENTIALS.get("reauth", True),
    )
    mock_docker_client.api.push.assert_called_once_with(
        repository=FAKE_IMAGE_NAME,
        tag=FAKE_TAG,
        stream=True,
        decode=True,
    )
    assert mock_stdout.write.call_count == 5


def test_push_docker_image_without_credentials(mock_docker_client, monkeypatch):
    # Mock stdout
    mock_stdout = MagicMock()
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    mock_docker_client.api.push.return_value = FAKE_EVENT

    result = push_docker_image(
        image_name=FAKE_IMAGE_NAME,
        tag=FAKE_TAG,
    )

    assert result["image_name"] == FAKE_IMAGE_NAME
    assert result["tag"] == FAKE_TAG
    assert result["image"] == f"{FAKE_IMAGE_NAME}:{FAKE_TAG}"

    mock_docker_client.login.assert_not_called()
    mock_docker_client.api.push.assert_called_once_with(
        repository=FAKE_IMAGE_NAME,
        tag=FAKE_TAG,
        stream=True,
        decode=True,
    )
    assert mock_stdout.write.call_count == 5


def test_push_docker_image_raises_on_event_error(mock_docker_client):
    error_event = [{"error": "Error"}]
    mock_docker_client.api.push.return_value = error_event

    with pytest.raises(OSError, match="Error"):
        push_docker_image(
            image_name=FAKE_IMAGE_NAME,
            tag=FAKE_TAG,
            credentials=FAKE_CREDENTIALS,
            ignore_cache=True,
        )


class TestCachedSteps:
    def test_cached_build_docker_image(self, mock_docker_client):
        image_name = "registry/repo"
        dockerfile = "Dockerfile"
        tag = "mytag"
        additional_tags = ["tag1", "tag2"]
        expected_result = {
            "image": f"{image_name}:{tag}",
            "tag": tag,
            "image_name": image_name,
            "image_id": FAKE_CONTAINER_ID,
            "additional_tags": additional_tags,
        }

        # Call the cached function multiple times with the same arguments
        for _ in range(3):
            result = build_docker_image(
                image_name=image_name,
                dockerfile=dockerfile,
                tag=tag,
                additional_tags=additional_tags,
            )
            assert result == expected_result

        # Assert that the Docker client methods are called only once
        mock_docker_client.api.build.assert_called_once()
        mock_docker_client.images.get.assert_called_once_with(FAKE_CONTAINER_ID)

        # Tag should be called once for the tag and once for each additional tag
        assert mock_docker_client.images.get.return_value.tag.call_count == 1 + len(
            additional_tags
        )

    def test_uncached_build_docker_image(self, mock_docker_client):
        image_name = "registry/repo"
        dockerfile = "Dockerfile"
        tag = "mytag"
        additional_tags = ["tag1", "tag2"]
        expected_result = {
            "image": f"{image_name}:{tag}",
            "tag": tag,
            "image_name": image_name,
            "image_id": FAKE_CONTAINER_ID,
            "additional_tags": additional_tags,
        }

        # Call the uncached function multiple times with the same arguments
        for _ in range(3):
            result = build_docker_image(
                image_name=image_name,
                dockerfile=dockerfile,
                tag=tag,
                additional_tags=additional_tags,
                ignore_cache=True,
            )
            assert result == expected_result

        # Assert that the Docker client methods are called for each function call
        assert mock_docker_client.api.build.call_count == 3
        assert mock_docker_client.images.get.call_count == 3
        expected_tag_calls = 1 + len(additional_tags)
        assert (
            mock_docker_client.images.get.return_value.tag.call_count
            == expected_tag_calls * 3
        )

    def test_cached_push_docker_image(self, mock_docker_client):
        image_name = FAKE_IMAGE_NAME
        tag = FAKE_TAG
        credentials = FAKE_CREDENTIALS
        additional_tags = FAKE_ADDITIONAL_TAGS
        expected_result = {
            "image_name": image_name,
            "tag": tag,
            "image": f"{image_name}:{tag}",
            "additional_tags": additional_tags,
        }

        for _ in range(2):
            result = push_docker_image(
                image_name=image_name,
                tag=tag,
                credentials=credentials,
                additional_tags=additional_tags,
            )
            assert result == expected_result

        mock_docker_client.login.assert_called_once()

        # Push should be called once for the tag and once for each additional tag
        assert mock_docker_client.api.push.call_count == 1 + len(additional_tags)

    def test_uncached_push_docker_image(self, mock_docker_client):
        image_name = FAKE_IMAGE_NAME
        tag = FAKE_TAG
        credentials = FAKE_CREDENTIALS
        additional_tags = FAKE_ADDITIONAL_TAGS
        expected_result = {
            "image_name": image_name,
            "tag": tag,
            "image": f"{image_name}:{tag}",
            "additional_tags": additional_tags,
        }

        # Call the uncached function multiple times with the same arguments
        for _ in range(3):
            result = push_docker_image(
                image_name=image_name,
                tag=tag,
                credentials=credentials,
                additional_tags=additional_tags,
                ignore_cache=True,
            )
            assert result == expected_result

        # Assert that the Docker client methods are called for each function call
        assert mock_docker_client.login.call_count == 3
        expected_push_calls = 1 + len(additional_tags)
        assert mock_docker_client.api.push.call_count == expected_push_calls * 3
