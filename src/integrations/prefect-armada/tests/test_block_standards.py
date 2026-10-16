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
        if to_qualified_name(block).startswith("prefect_armada")
    ]
    return module_blocks


@pytest.mark.parametrize("block", find_module_blocks())
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        return block

    def test_has_a_valid_image(self, block: type[Block]) -> None:
        pytest.skip(
            "prefect-armada does not have a hosted block logo yet; see "
            "https://github.com/PrefectHQ/prefect/tree/main/src/integrations/prefect-armada"
        )
