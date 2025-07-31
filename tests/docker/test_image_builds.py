import io
import re
import sys
from pathlib import Path, PurePosixPath
from textwrap import dedent

import pytest
from _pytest.capture import CaptureFixture

import prefect
from prefect.utilities.dockerutils import (
    BuildError,
    ImageBuilder,
    build_image,
    generate_default_dockerfile,
    get_prefect_image_name,
    silence_docker_warnings,
)

with silence_docker_warnings():
    from docker import DockerClient

IMAGE_ID_PATTERN = re.compile("^sha256:[a-fA-F0-9]{64}$")


pytestmark = [pytest.mark.service("docker"), pytest.mark.timeout(120.0)]


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent / "contexts"


def test_builds_tiny_hello_image(contexts: Path, docker: DockerClient):
    image_id = build_image(contexts / "tiny")
    assert IMAGE_ID_PATTERN.match(image_id)

    image = docker.images.get(image_id)
    assert image

    output = docker.containers.run(image, remove=True)
    assert output == b"Can't bear oceans.\n"


def test_build_with_tag(contexts: Path, docker: DockerClient):
    image_id = build_image(contexts / "tiny", tag="test:latest")
    assert IMAGE_ID_PATTERN.match(image_id)

    image = docker.images.get(image_id)
    assert image.tags == ["test:latest"]


def test_builds_alternate_dockerfiles(contexts: Path, docker: DockerClient):
    image_a = build_image(contexts / "alternate", dockerfile="Dockerfile.a")
    assert IMAGE_ID_PATTERN.match(image_a)

    output = docker.containers.run(image_a, remove=True)
    assert output == b"from Dockerfile.a!\n"

    image_b = build_image(contexts / "alternate", dockerfile="Dockerfile.b")
    assert IMAGE_ID_PATTERN.match(image_b)

    assert image_a != image_b

    output = docker.containers.run(image_b, remove=True)
    assert output == b"from Dockerfile.b!\n"


def test_streams_progress_nowhere_by_default(contexts: Path, capsys: CaptureFixture):
    image_id = build_image(contexts / "tiny")
    assert IMAGE_ID_PATTERN.match(image_id)

    captured = capsys.readouterr()
    assert not captured.err
    assert not captured.out


def test_streams_progress_to_stdout(contexts: Path, capsys: CaptureFixture):
    image_id = build_image(contexts / "tiny", stream_progress_to=sys.stdout)
    assert IMAGE_ID_PATTERN.match(image_id)

    captured = capsys.readouterr()
    assert not captured.err

    output = captured.out

    # spot check a few things we should expect to find in the output
    assert "COPY hello.txt" in output

    _, _, image_hash = image_id.partition(":")
    assert f"Successfully built {image_hash[:12]}" in output


def test_streams_progress_to_given_stream(contexts: Path):
    my_stream = io.StringIO()

    image_id = build_image(contexts / "tiny", stream_progress_to=my_stream)
    assert IMAGE_ID_PATTERN.match(image_id)

    output = my_stream.getvalue()

    # spot check a few things we should expect to find in the output
    assert "COPY hello.txt" in output

    _, _, image_hash = image_id.partition(":")
    assert f"Successfully built {image_hash[:12]}" in output


def test_requires_path(contexts: Path):
    with pytest.raises(ValueError, match="context required"):
        build_image(None)


def test_requires_existing_path(contexts: Path):
    with pytest.raises(ValueError, match="does not exist"):
        build_image(contexts / "missing")


def test_requires_real_dockerfile(contexts: Path):
    with pytest.raises(BuildError, match="Cannot locate specified Dockerfile"):
        build_image(contexts / "tiny", dockerfile="Nowhere")


@pytest.mark.parametrize(
    "example_context, expected_error",
    [
        ("bad-base", "pull access denied"),
        ("broken", "returned a non-zero code"),
        ("missing-file", "COPY failed"),
    ],
)
def test_raises_exception_on_bad_base_image(
    contexts: Path, example_context: str, expected_error: str
):
    # Occasionally, Dockerhub will rate limit us and return a 429
    # so we will allow this as an acceptable error since we know that
    # the image pull attempt occurred. For this same reason we also
    # allow 500 errors to be acceptable.
    with pytest.raises(BuildError, match=expected_error + "|429" + "|500"):
        build_image(contexts / example_context, stream_progress_to=sys.stdout)


def test_image_builder_must_be_entered(contexts: Path):
    builder = ImageBuilder(base_image="busybox")
    with pytest.raises(Exception, match="No context available"):
        builder.copy(contexts / "tiny" / "hello.txt", "hello.txt")


def test_image_builder_allocates_temporary_context(prefect_base_image: str):
    with ImageBuilder(prefect_base_image) as image:
        assert image.context
        assert image.context.exists()
        context = image.context

    assert not image.context
    assert not context.exists()


def test_image_builder_accepts_alternative_base_image():
    with ImageBuilder("busybox") as image:
        assert image.dockerfile_lines == ["FROM busybox"]


def test_from_prefect_image(docker: DockerClient, prefect_base_image: str):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("RUN echo Woooo, building")
        image.add_line('ENTRYPOINT [ "prefect", "--version" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == prefect.__version__


def test_copying_file(contexts: Path, docker: DockerClient, prefect_base_image: str):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy(contexts / "tiny" / "hello.txt", "hello.txt")
        image.add_line('ENTRYPOINT [ "/bin/cat", "hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_copied_paths_are_resolved(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy(contexts / "tiny" / ".." / "tiny" / "hello.txt", "hello.txt")
        image.add_line('ENTRYPOINT [ "/bin/cat", "hello.txt" ]')
        image_id = image.build()

        image.assert_has_line("COPY tests/docker/contexts/tiny/hello.txt hello.txt")

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_copying_file_to_absolute_location(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy(contexts / "tiny" / "hello.txt", "/hello.txt")
        image.add_line('ENTRYPOINT [ "/bin/cat", "/hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_copying_file_to_posix_path(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy(contexts / "tiny" / "hello.txt", PurePosixPath("/hello.txt"))
        image.add_line('ENTRYPOINT [ "/bin/cat", "/hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_copying_directory(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy(contexts / "tiny", "tiny")
        image.add_line('ENTRYPOINT [ "/bin/cat", "tiny/hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_copying_directory_to_absolute_location(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(prefect_base_image) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy(contexts / "tiny", "/tiny")
        image.add_line('ENTRYPOINT [ "/bin/cat", "/tiny/hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_copying_file_from_alternative_base(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(prefect_base_image, base_directory=contexts / "tiny") as image:
        image.add_line("WORKDIR /tiny/")
        image.copy("hello.txt", "hello.txt")
        image.add_line('ENTRYPOINT [ "/bin/cat", "hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_can_use_working_tree_as_context(
    contexts: Path, docker: DockerClient, prefect_base_image: str
):
    with ImageBuilder(
        prefect_base_image, context=contexts / "tree-as-context"
    ) as image:
        image.add_line("WORKDIR /tiny/")
        image.copy("hello.txt", "hello.txt")
        image.add_line('ENTRYPOINT [ "/bin/cat", "hello.txt" ]')
        image_id = image.build()

    output = docker.containers.run(image_id, remove=True).decode().strip()
    assert output == "Can't bear oceans."


def test_cannot_already_have_a_dockerfile_in_context(
    contexts: Path, prefect_base_image: str
):
    with pytest.raises(ValueError, match="already a Dockerfile"):
        ImageBuilder(prefect_base_image, context=contexts / "tiny")


def test_generate_dockerfile_with_no_requirements(contexts):
    with generate_default_dockerfile(contexts / "no-dockerfile") as dockerfile:
        assert dockerfile.exists()
        assert dockerfile.read_text() == dedent(
            f"""\
                    FROM {get_prefect_image_name()}
                    COPY . /opt/prefect/no-dockerfile/
                    WORKDIR /opt/prefect/no-dockerfile/
                    """
        )

    assert not dockerfile.exists()


def test_generate_dockerfile_with_requirements(contexts):
    with generate_default_dockerfile(contexts / "requirements") as dockerfile:
        assert dockerfile.exists()
        assert dockerfile.read_text() == dedent(
            f"""\
                    FROM {get_prefect_image_name()}
                    COPY requirements.txt /opt/prefect/requirements/requirements.txt
                    RUN uv pip install -r /opt/prefect/requirements/requirements.txt
                    COPY . /opt/prefect/requirements/
                    WORKDIR /opt/prefect/requirements/
                    """
        )
