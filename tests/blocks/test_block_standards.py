import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.utilities.dispatch import get_registry_for_type

block_registry = get_registry_for_type(Block) or {}


@pytest.mark.parametrize(
    "block", sorted(block_registry.values(), key=lambda x: x.get_block_type_slug())
)
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        return block
