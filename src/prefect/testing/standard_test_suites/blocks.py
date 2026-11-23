import re
import subprocess
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import IO
from urllib.request import urlopen

import pytest

from prefect.blocks.core import Block

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_REPO_ASSET_URL_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/PrefectHQ/prefect/(?P<sha>[0-9a-f]{40})/(?P<path>assets/.+)$"
)


def _read_local_repo_asset(url: str) -> bytes | None:
    """
    Return the contents of a logo URL that points at an asset in this repository
    pinned to a commit, read at that commit from the git repository containing
    this file (an editable install, or a virtualenv inside a checkout).

    Returns `None` if the URL doesn't point at a pinned repository asset or the
    local checkout can't provide it (e.g. `prefect` is installed from a wheel, the
    clone is shallow, or the commit or path doesn't exist).
    """
    match = _REPO_ASSET_URL_PATTERN.match(url)
    if match is None:
        return None
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(Path(__file__).parent),
                "cat-file",
                "blob",
                f"{match.group('sha')}:{match.group('path')}",
            ],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _open_logo(url: str) -> IO[bytes]:
    # Read repository-hosted logos from the local git checkout instead of
    # raw.githubusercontent.com, which intermittently rejects requests from CI
    # (e.g. `503 Backend.max_conn reached`) and makes this test flaky. Reading
    # the blob at the pinned commit yields the same bytes the URL serves.
    if (content := _read_local_repo_asset(url)) is not None:
        return BytesIO(content)
    return urlopen(url)


class BlockStandardTestSuite(ABC):
    @pytest.fixture
    @abstractmethod
    def block(self) -> type[Block]:
        pass

    def test_has_a_description(self, block: type[Block]) -> None:
        assert block.get_description()

    def test_has_a_documentation_url(self, block: type[Block]) -> None:
        assert block._documentation_url

    def test_all_fields_have_a_description(self, block: type[Block]) -> None:
        for name, field in block.model_fields.items():
            if Block.annotation_refers_to_block_class(field.annotation):
                # TODO: Block field descriptions aren't currently handled by the UI, so
                # block fields are currently excluded from this test. Once block field
                # descriptions are supported by the UI, remove this clause.
                continue
            assert field.description, (
                f"{block.__name__} is missing a description on {name}"
            )
            assert field.description.endswith("."), (
                f"{name} description on {block.__name__} does not end with a period"
            )

    def test_has_a_valid_code_example(self, block: type[Block]) -> None:
        code_example = block.get_code_example()
        assert code_example is not None, f"{block.__name__} is missing a code example"

        # Extract base name without generic parameters
        base_name = block.__name__.partition("[")[0]

        # Check for proper import statement
        import_pattern = rf"from .* import {base_name}"
        assert re.search(import_pattern, code_example) is not None, (
            f"The code example for {base_name} is missing an import statement"
            f" matching the pattern {import_pattern}"
        )

        # Check for proper load statement
        block_load_pattern = rf'.* = {base_name}\.load\("BLOCK_NAME"\)'
        assert re.search(block_load_pattern, code_example), (
            f"The code example for {base_name} is missing a .load statement"
            f" matching the pattern {block_load_pattern}"
        )

    @pytest.mark.skipif(not HAS_PIL, reason="PIL/Pillow is not available")
    def test_has_a_valid_image(self, block: type[Block]) -> None:
        logo_url = block._logo_url
        assert logo_url is not None, (
            f"{block.__name__} is missing a value for _logo_url"
        )
        with _open_logo(str(logo_url)) as logo:
            img = Image.open(logo)
            img.load()
        assert img.width == img.height, "Logo should be a square image"
        assert 1000 > img.width > 45, (
            f"Logo should be between 200px and 1000px wid, but is {img.width}px wide"
        )
