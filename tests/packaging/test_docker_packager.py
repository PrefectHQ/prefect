import re
import textwrap
from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo

import pytest
from docker import DockerClient
from docker.models.containers import Container

import prefect
from prefect.client import OrionClient
from prefect.deployments import Deployment
from prefect.flow_runners.docker import DockerFlowRunner
from prefect.orion.schemas.states import StateType
from prefect.packaging.docker import DockerPackageManifest, DockerPackager
from prefect.software.python import PythonEnvironment

pytestmark = pytest.mark.service("docker")


IMAGE_ID_PATTERN = re.compile("^sha256:[a-fA-F0-9]{64}$")


@prefect.flow
def howdy() -> str:
    import requests

    assert requests.__version__ == "2.28.0"

    return "howdy!"


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent.parent / "docker" / "contexts"


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


async def test_custom_dockerfile_unpackaging(contexts: Path, docker: DockerClient):
    packager = DockerPackager(
        dockerfile=contexts / "howdy-flow" / "Dockerfile",
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

    assert flow().result() == 'howdy!'
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


async def test_end_to_end(
    use_hosted_orion, prefect_base_image: str, orion_client: OrionClient
):
    deployment = Deployment(
        name="howdy-deployed",
        flow=howdy,
        packager=DockerPackager(
            base_image=prefect_base_image,
            python_environment=PythonEnvironment(
                python_version="3.9",
                pip_requirements=["requests==2.28.0"],
            ),
        ),
    )
    deployment_id = await deployment.create()

    server_deployment = await orion_client.read_deployment(deployment_id)
    manifest: DockerPackageManifest = server_deployment.flow_data.decode()
    runner = DockerFlowRunner(image=manifest.image)

    flow_run = await orion_client.create_flow_run_from_deployment(deployment_id)

    assert await runner.submit_flow_run(flow_run)

    flow_run = await orion_client.read_flow_run(flow_run.id)
    assert flow_run.state.type == StateType.COMPLETED, flow_run.state.message
