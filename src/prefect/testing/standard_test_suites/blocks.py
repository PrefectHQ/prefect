from abc import ABC, abstractmethod
from typing import Type

import pytest

from prefect.blocks.core import Block


class BlockStandardTestSuite(ABC):
    @pytest.fixture
    @abstractmethod
    def block(self) -> Type[Block]:
        pass

    def test_all_fields_have_a_description(self, block: Type[Block]):
        for name, field in block.__fields__.items():
            assert (
                field.field_info.description
            ), f"{block.__name__} is missing a description on {name}"
