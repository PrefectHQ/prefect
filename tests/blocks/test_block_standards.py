import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.testing.standard_test_suites.blocks import _read_local_repo_asset
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


def test_repository_hosted_logos_resolve_to_local_assets():
    repo_hosted_logo_urls = {
        str(block._logo_url)
        for block in blocks_under_test
        if block._logo_url is not None
        and str(block._logo_url).startswith(
            "https://raw.githubusercontent.com/PrefectHQ/prefect/"
        )
    }
    assert repo_hosted_logo_urls
    for url in repo_hosted_logo_urls:
        assert _read_local_repo_asset(url), url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/assets/block-logos/slack.png",
        "https://raw.githubusercontent.com/PrefectHQ/prefect/main/assets/block-logos/slack.png",
        # nonexistent commit
        "https://raw.githubusercontent.com/PrefectHQ/prefect/0000000000000000000000000000000000000000/assets/block-logos/slack.png",
        # nonexistent path at a real commit
        "https://raw.githubusercontent.com/PrefectHQ/prefect/420d0d6a78bb6df1fc18bcf188fdad43c1d22ea9/assets/block-logos/does-not-exist.png",
    ],
)
def test_logos_not_in_the_local_repository_are_not_resolved_locally(url: str):
    assert _read_local_repo_asset(url) is None
