from pathlib import Path

import pytest

from prefect.testing.docker import capture_builders
from prefect.utilities.dockerutils import ImageBuilder


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent / "contexts"


@pytest.fixture
def builder():
    with ImageBuilder("busybox") as builder:
        builder.add_line("RUN false")  # this confirms that we aren't building the image
        yield builder


def test_can_capture_builder(contexts: Path):
    def example_image_building_method(contexts: Path):
        with ImageBuilder("some-base") as image:
            image.add_line("RUN marvinsay 'I can see by infra-red'")
            image.copy(contexts / "tiny" / "hello.txt", "/hello.txt")

    with capture_builders() as builder_list:
        assert len(builder_list) == 0

        example_image_building_method(contexts)

    assert len(builder_list) == 1
    (last_builder,) = builder_list

    last_builder.assert_has_line("FROM some-base")
    last_builder.assert_has_line("RUN marvinsay 'I can see by infra-red'")
    last_builder.assert_has_file(contexts / "tiny" / "hello.txt", "/hello.txt")


def test_can_assert_about_lines_in_dockerfile(builder: ImageBuilder):
    builder.add_line("ENTRYPOINT busted")

    builder.assert_has_line("ENTRYPOINT busted")
    with pytest.raises(AssertionError, match="Unexpected 'ENTRYPOINT busted' "):
        builder.assert_line_absent("ENTRYPOINT busted")

    builder.assert_line_absent("FOO bar")
    with pytest.raises(AssertionError, match="Expected 'FOO bar'"):
        builder.assert_has_line("FOO bar")


def test_can_assert_about_line_order(builder: ImageBuilder):
    builder.add_line("RUN first")
    builder.add_line("RUN something else")
    builder.add_line("RUN second")

    builder.assert_line_before("RUN first", "RUN second")
    with pytest.raises(AssertionError, match="Expected 'RUN second' to appear"):
        builder.assert_line_before("RUN second", "RUN first")

    builder.assert_line_after("RUN second", "RUN first")
    with pytest.raises(AssertionError, match="Expected 'RUN second' to appear"):
        builder.assert_line_after("RUN first", "RUN second")


def test_can_assert_about_file_copies(builder: ImageBuilder, contexts: Path):
    builder.copy(contexts / "tiny" / "hello.txt", "/hello.txt")

    builder.assert_has_file(contexts / "tiny" / "hello.txt", "/hello.txt")


def test_can_assert_about_directory_copies(builder: ImageBuilder, contexts: Path):
    builder.copy(contexts / "tiny", "/tiny")

    builder.assert_has_file(contexts / "tiny", "/tiny")
