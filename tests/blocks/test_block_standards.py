import json
from urllib.error import HTTPError
from urllib.parse import urlparse

import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.testing.standard_test_suites.blocks import HAS_PIL
from prefect.utilities.dispatch import get_registry_for_type
from prefect.utilities.importtools import to_qualified_name

block_registry = get_registry_for_type(Block) or {}

blocks_under_test = [
    block
    for block in block_registry.values()
    if to_qualified_name(block).startswith("prefect.")
]


@pytest.mark.parametrize(
    "block", sorted(blocks_under_test, key=lambda x: x.get_block_type_slug())
)
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        return block

    @pytest.mark.skipif(not HAS_PIL, reason="PIL/Pillow is not available")
    def test_has_a_valid_image(self, block: type[Block]) -> None:
        try:
            super().test_has_a_valid_image(block)
        except HTTPError as exc:
            url = urlparse(str(block._logo_url))
            if (
                exc.code != 402
                or url.hostname != "cdn.sanity.io"
                or not url.path.startswith("/images/3ugk85nk/production/")
            ):
                raise
            try:
                with exc:
                    response = json.load(exc)
            except (ValueError, UnicodeDecodeError):
                raise exc from None
            if (
                isinstance(response, dict)
                and response.get("error") == "Project Disabled"
                and response.get("message")
                == "This project has been disabled by a project administrator"
            ):
                pytest.xfail(
                    "Sanity project 3ugk85nk is disabled; restore the project or migrate block logos"
                )
            raise
