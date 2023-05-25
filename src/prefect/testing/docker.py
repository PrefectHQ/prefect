from contextlib import contextmanager
from typing import Generator, List
from unittest import mock

from prefect.utilities.dockerutils import ImageBuilder


@contextmanager
def capture_builders() -> Generator[List[ImageBuilder], None, None]:
    """Captures any instances of ImageBuilder created while this context is active"""
    builders = []

    original_init = ImageBuilder.__init__

    def capture(self, *args, **kwargs):
        builders.append(self)
        original_init(self, *args, **kwargs)

    with mock.patch.object(ImageBuilder, "__init__", capture):
        yield builders
