import re
import textwrap
import warnings
from io import BytesIO
from pathlib import Path, PurePosixPath
from tarfile import TarFile, TarInfo

import pytest

from prefect.packaging.docker import DockerPackageManifest, DockerPackager
from prefect.software.conda import CondaEnvironment
from prefect.software.python import PythonEnvironment
from prefect.utilities.callables import parameter_schema
from prefect.utilities.dockerutils import (
    get_prefect_image_name,
    silence_docker_warnings,
)

from . import howdy

pytestmark = [
    pytest.mark.skip(reason="These tests are incredibly brittle and causing noise."),
    pytest.mark.timeout(120.0),
]
with silence_docker_warnings():
    from docker import DockerClient
    from docker.models.containers import Container

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


def test_base_image_defaults_to_prefect_base():
    packager = DockerPackager()
    assert packager.base_image == get_prefect_image_name()


def test_base_image_defaults_to_conda_flavor_of_prefect_base():
    packager = DockerPackager(python_environment=CondaEnvironment())
    assert packager.base_image == get_prefect_image_name(flavor="conda")


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

    # Test the string representations of the path object because
    # on Windows, we'll get a WindowsPath object, which isn't
    # comparable to a PurePosixPath.
    assert str(packager.dockerfile) == str(PurePosixPath("Docky"))
    assert not packager.python_environment


@pytest.mark.service("docker")
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


@pytest.mark.service("docker")
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


@pytest.mark.service("docker")
async def test_packaging_a_flow_to_registry_without_scheme(
    prefect_base_image: str, registry: str
):
    packager = DockerPackager(
        base_image=prefect_base_image,
        python_environment=PythonEnvironment(
            python_version="3.9",
            pip_requirements=["requests==2.28.0"],
        ),
        registry_url="localhost:5555",
    )

    manifest = await packager.package(howdy)

    assert isinstance(manifest, DockerPackageManifest)
    assert manifest.image.startswith("localhost:5555/howdy:")
    assert manifest.image_flow_location == "/flow.py"
    assert manifest.flow_name == "howdy"


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


@pytest.mark.service("docker")
async def test_unpackaging_outside_container(howdy_context: Path):
    # This test is contrived to pretend we're in a Docker container right now and giving
    # a known test file path as the image_flow_location
    packager = DockerPackager(
        dockerfile=howdy_context / "Dockerfile",
        image_flow_location=str(howdy_context / "howdy.py"),
    )
    manifest = await packager.package(howdy)

    unpackaged_howdy = await manifest.unpackage()
    assert unpackaged_howdy("dude") == "howdy, dude!"


@pytest.mark.service("docker")
async def test_packager_sets_manifest_flow_parameter_schema(howdy_context: Path):
    packager = DockerPackager(
        dockerfile=howdy_context / "Dockerfile",
        image_flow_location=str(howdy_context / "howdy.py"),
    )
    manifest = await packager.package(howdy)
    assert manifest.flow_parameter_schema == parameter_schema(howdy.fn)


@pytest.mark.service("docker")
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


@pytest.mark.service("docker")
async def test_custom_dockerfile_unpackaging(howdy_context: Path, docker: DockerClient):
    packager = DockerPackager(
        dockerfile=howdy_context / "Dockerfile",
        image_flow_location="/howdy.py",
    )
    manifest = await packager.package(howdy)
    assert_unpackaged_flow_works(docker, manifest)


@pytest.mark.service("docker")
def assert_unpackaged_flow_works(docker: DockerClient, manifest: DockerPackageManifest):
    test_script = textwrap.dedent(
        f"""
    import asyncio
    from prefect.packaging.docker import DockerPackageManifest

    manifest = DockerPackageManifest.parse_raw({manifest.json()!r})

    flow = asyncio.get_event_loop().run_until_complete(manifest.unpackage())

    assert flow('there') == 'howdy, there!'
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
