import re
import textwrap
import warnings
from io import BytesIO
from pathlib import Path, PurePosixPath
from tarfile import TarFile, TarInfo

import pytest

from prefect.client import OrionClient
from prefect.deployments import Deployment
from prefect.docker import Container, DockerClient
from prefect.flow_runners.docker import DockerFlowRunner
from prefect.packaging.docker import DockerPackageManifest, DockerPackager
from prefect.software.python import PythonEnvironment

from . import howdy

pytestmark = pytest.mark.service("docker")


IMAGE_ID_PATTERN = re.compile("^sha256:[a-fA-F0-9]{64}$")


@pytest.fixture(autouse=True)
def silence_user_warnings_about_editable_packages():
    # For the duration of these tests, ignore our UserWarning coming from
    # prefect.software.pip.current_environment_requirements about editable packages;
    # when working locally, the prefect package is almost always editable
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The following requirements will not be installable.*",
            category=UserWarning,
            module="prefect.software.pip",
        )
        yield


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent.parent / "docker" / "contexts"


def test_building_or_dockerfile_required():
    with pytest.raises(ValueError, match="One of `base_image` or `dockerfile`"):
        DockerPackager(base_image=None, dockerfile=None)


def test_dockerfile_exclusive_with_building():
    with pytest.raises(ValueError, match="Either `base_image` or `dockerfile`"):
        DockerPackager(base_image="yep", dockerfile="nope")


def test_python_environment_autodetected_when_building():
    packager = DockerPackager(base_image="yep", python_environment=None)
    assert packager.base_image == "yep"
    assert packager.python_environment
    assert packager.python_environment.pip_requirements


def test_python_environment_not_autodetected_with_dockerfile():
    packager = DockerPackager(dockerfile="Docky")
    assert packager.dockerfile == PurePosixPath("Docky")
    assert not packager.python_environment


async def test_packaging_a_flow_to_local_docker_daemon(prefect_base_image: str):
    packager = DockerPackager(
        base_image=prefect_base_image,
        python_environment=PythonEnvironment(
            python_version="3.9",
            pip_requirements=["requests==2.28.0"],
        ),
    )

    manifest = await packager.package(howdy)

    assert isinstance(manifest, DockerPackageManifest)
    assert IMAGE_ID_PATTERN.match(manifest.image)
    assert manifest.image_flow_location == "/flow.py"
    assert manifest.flow_name == "howdy"


async def test_packaging_a_flow_to_registry(prefect_base_image: str, registry: str):
    packager = DockerPackager(
        base_image=prefect_base_image,
        python_environment=PythonEnvironment(
            python_version="3.9",
            pip_requirements=["requests==2.28.0"],
        ),
        registry_url=registry,
    )

    manifest = await packager.package(howdy)

    assert isinstance(manifest, DockerPackageManifest)
    assert manifest.image.startswith("localhost:5555/howdy:")
    assert manifest.image_flow_location == "/flow.py"
    assert manifest.flow_name == "howdy"


async def test_creating_deployments(prefect_base_image: str, orion_client: OrionClient):
    deployment = Deployment(
        name="howdy-deployed",
        flow=howdy,
        flow_runner=DockerFlowRunner(),
        packager=DockerPackager(
            base_image=prefect_base_image,
            python_environment=PythonEnvironment(
                python_version="3.9",
                pip_requirements=["requests==2.28.0"],
            ),
        ),
    )
    deployment_id = await deployment.create()

    roundtripped = await orion_client.read_deployment(deployment_id)
    assert roundtripped.flow_data.encoding == "package-manifest"

    manifest = DockerPackageManifest.parse_raw(roundtripped.flow_data.blob)
    assert IMAGE_ID_PATTERN.match(manifest.image)


@pytest.fixture
def howdy_context(prefect_base_image: str, tmp_path: Path) -> Path:
    (tmp_path / "Dockerfile").write_text(
        textwrap.dedent(
            f"""
            FROM {prefect_base_image}
            COPY howdy.py /howdy.py
            """
        )
    )

    (tmp_path / "howdy.py").write_text(
        textwrap.dedent(
            """
            from prefect import flow


            @flow
            def howdy(name: str) -> str:
                return f"howdy, {name}!"
            """
        )
    )

    return tmp_path


async def test_unpackaging_outside_container(howdy_context: Path):
    # This test is contrived to pretend we're in a Docker container right now and giving
    # a known test file path as the image_flow_location
    manifest = DockerPackageManifest(
        image="any-one",
        image_flow_location=str(howdy_context / "howdy.py"),
        flow_name="howdy",
    )
    unpackaged_howdy = await manifest.unpackage()
    assert unpackaged_howdy("dude").result() == "howdy, dude!"


async def test_unpackaging_inside_container(
    prefect_base_image: str, docker: DockerClient
):
    packager = DockerPackager(
        base_image=prefect_base_image,
        python_environment=PythonEnvironment(
            python_version="3.9",
            pip_requirements=["requests==2.28.0"],
        ),
    )
    manifest = await packager.package(howdy)
    assert_unpackaged_flow_works(docker, manifest)


async def test_custom_dockerfile_unpackaging(howdy_context: Path, docker: DockerClient):
    packager = DockerPackager(
        dockerfile=howdy_context / "Dockerfile",
        image_flow_location="/howdy.py",
    )
    manifest = await packager.package(howdy)
    assert_unpackaged_flow_works(docker, manifest)


def assert_unpackaged_flow_works(docker: DockerClient, manifest: DockerPackageManifest):
    test_script = textwrap.dedent(
        f"""
    import asyncio
    from prefect.packaging.docker import DockerPackageManifest

    manifest = DockerPackageManifest.parse_raw({manifest.json()!r})

    flow = asyncio.get_event_loop().run_until_complete(manifest.unpackage())

    assert flow('there').result() == 'howdy, there!'
    """
    )

    container: Container = docker.containers.create(
        manifest.image,
        command="python /tmp/test.py",
    )
    try:
        buffer = BytesIO()
        with TarFile(mode="w", fileobj=buffer) as script_tarball:
            script_bytes = test_script.encode()
            info = TarInfo("test.py")
            info.size = len(script_bytes)
            script_tarball.addfile(info, BytesIO(script_bytes))

        container.put_archive("/tmp", buffer.getvalue())

        container.start()
        response = container.wait()
        output = container.logs().decode()
        assert response["StatusCode"] == 0, output
    finally:
        container.remove(force=True)
