import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.testing.standard_test_suites.blocks import _local_repo_asset
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
        path = _local_repo_asset(url)
        assert path is not None, url
        assert url.endswith(path.relative_to(path.parents[2]).as_posix())


def test_non_repository_logos_are_not_resolved_locally():
    assert _local_repo_asset("https://example.com/assets/block-logos/slack.png") is None
    assert (
        _local_repo_asset(
            "https://raw.githubusercontent.com/PrefectHQ/prefect/main/assets/block-logos/slack.png"
        )
        is None
    )
