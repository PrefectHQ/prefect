"""Every Block this package ships must satisfy Prefect's block conventions.

`BlockStandardTestSuite` is Prefect's own suite. It enforces the metadata the
Prefect UI and `prefect block register` depend on: a description, a
documentation URL, a description ending in a period on every field, a code
example that shows `.load("BLOCK_NAME")`, and a square logo.
"""

from __future__ import annotations

import io
from urllib.request import urlopen

import prefect_sandbox  # noqa: F401  -- importing the package is what registers its Blocks
import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.utilities.dispatch import get_registry_for_type
from prefect.utilities.importtools import to_qualified_name

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def find_module_blocks() -> list[type[Block]]:
    """Collect the concrete Block subclasses this package contributes."""
    blocks = get_registry_for_type(Block) or {}
    return [
        block
        for block in blocks.values()
        if to_qualified_name(block).startswith("prefect_sandbox")
        # A Block interface is not a block type: Prefect refuses to register one
        # (`InvalidBlockRegistration`), so it can never satisfy the suite's
        # `.load("BLOCK_NAME")` example. Dispatch already withholds classes with
        # `ABC` directly in `__bases__` — which covers `SandboxBackend` — but a
        # subclass that merely *inherits* unimplemented abstract methods does get
        # registered, and would fail the suite for the wrong reason.
        and not getattr(block, "__abstractmethods__", frozenset())
    ]


@pytest.mark.parametrize(
    "block", sorted(find_module_blocks(), key=lambda block: block.get_block_type_slug())
)
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block: type[Block]) -> type[Block]:
        return block

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow is not installed")
    def test_has_a_valid_image(self, block: type[Block]) -> None:
        """Assert the logo is declared, and check its shape when reachable.

        Overrides the upstream check, which fetches `_logo_url` with `urlopen`
        and therefore fails on an offline clone or a network-restricted runner —
        an outcome that says nothing about the code under test. The half that is
        genuinely this package's contract (a logo is declared at all) stays a
        hard assertion; only the dimension check, which is impossible without
        the bytes, degrades to a skip when the fetch cannot complete. Decoding
        happens outside the `try` so a URL that serves something that is not an
        image still fails.
        """
        logo_url = block._logo_url
        assert logo_url is not None, (
            f"{block.__name__} is missing a value for _logo_url"
        )

        try:
            with urlopen(str(logo_url), timeout=10) as response:
                payload = response.read()
        except OSError as exc:  # URLError, HTTPError, and socket timeouts
            pytest.skip(f"Could not fetch {logo_url}: {exc}")

        image = Image.open(io.BytesIO(payload))
        assert image.width == image.height, "Logo should be a square image"
        assert 1000 > image.width > 45, (
            f"Logo should be between 45px and 1000px wide, but is {image.width}px wide"
        )
