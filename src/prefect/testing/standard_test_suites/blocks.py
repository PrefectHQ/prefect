import re
from abc import ABC, abstractmethod
from typing import Type

import pytest

from prefect.blocks.core import Block


class BlockStandardTestSuite(ABC):
    @pytest.fixture
    @abstractmethod
    def block(self) -> Type[Block]:
        pass

    def test_has_a_description(self, block: Type[Block]):
        assert block.get_description()

    def test_all_fields_have_a_description(self, block: Type[Block]):
        for name, field in block.__fields__.items():
            if Block.is_block_class(field.type_):
                # TODO: Block field descriptions aren't currently handled by the UI, so block
                # fields are currently excluded from this test. Once block field descriptions are
                # supported by the UI, remove this clause.
                continue
            assert (
                field.field_info.description
            ), f"{block.__name__} is missing a description on {name}"
            assert field.field_info.description.endswith(
                "."
            ), f"{name} description on {block.__name__} does not end with a period"

    def test_has_a_valid_code_example(self, block: Type[Block]):
        code_example = block.get_code_example()
        assert code_example is not None, f"{block.__name__} is missing a code example"
        import_pattern = rf"from .* import {block.__name__}"
        assert (
            re.search(import_pattern, code_example) is not None
        ), f"The code example for {block.__name__} is missing an import statement matching the pattern {import_pattern}"
        block_load_pattern = rf'.* = {block.__name__}\.load\("BLOCK_NAME"\)'
        assert re.search(
            block_load_pattern, code_example
        ), f"The code example for {block.__name__} is missing a .load statement matching the pattern {block_load_pattern}"
