import pytest

from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.utilities.dispatch import get_registry_for_type
from prefect.utilities.importtools import to_qualified_name


def find_module_blocks():
    blocks = get_registry_for_type(Block)
    module_blocks = [
        block
        for block in blocks.values()
        if to_qualified_name(block).startswith("prefect_shell")
        # `ShellOperation(JobBlock[list[str]])` registers the parametrized
        # `JobBlock[list[str]]` too, which is not a block of this package
        and not block.__pydantic_generic_metadata__["origin"]
    ]
    return module_blocks


@pytest.mark.parametrize("block", find_module_blocks())
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        return block
