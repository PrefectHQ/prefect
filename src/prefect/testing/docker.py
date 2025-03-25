from contextlib import contextmanager
from typing import Any, Generator
from unittest import mock

from prefect.utilities.dockerutils import ImageBuilder


@contextmanager
def capture_builders() -> Generator[list[ImageBuilder], None, None]:
    """Captures any instances of ImageBuilder created while this context is active"""
    builders: list[ImageBuilder] = []

    original_init = ImageBuilder.__init__

    def capture(self: ImageBuilder, *args: Any, **kwargs: Any):
        builders.append(self)
        original_init(self, *args, **kwargs)

    with mock.patch.object(ImageBuilder, "__init__", capture):
        yield builders
