import re
from abc import ABC, abstractmethod
from typing import Type
from urllib.request import urlopen

import pytest
from PIL import Image

from prefect.blocks.core import Block


class BlockStandardTestSuite(ABC):
    @pytest.fixture
    @abstractmethod
    def block(self) -> Type[Block]:
        pass

    def test_has_a_description(self, block: Type[Block]):
        assert block.get_description()

    def test_has_a_documentation_url(self, block: Type[Block]):
        assert block._documentation_url

    def test_all_fields_have_a_description(self, block: Type[Block]):
        for name, field in block.model_fields.items():
            if Block.annotation_refers_to_block_class(field.annotation):
                # TODO: Block field descriptions aren't currently handled by the UI, so
                # block fields are currently excluded from this test. Once block field
                # descriptions are supported by the UI, remove this clause.
                continue
            assert (
                field.description
            ), f"{block.__name__} is missing a description on {name}"
            assert field.description.endswith(
                "."
            ), f"{name} description on {block.__name__} does not end with a period"

    def test_has_a_valid_code_example(self, block: Type[Block]):
        code_example = block.get_code_example()
        assert code_example is not None, f"{block.__name__} is missing a code example"
        import_pattern = rf"from .* import {block.__name__}"
        assert re.search(import_pattern, code_example) is not None, (
            f"The code example for {block.__name__} is missing an import statement"
            f" matching the pattern {import_pattern}"
        )
        block_load_pattern = rf'.* = {block.__name__}\.load\("BLOCK_NAME"\)'
        assert re.search(block_load_pattern, code_example), (
            f"The code example for {block.__name__} is missing a .load statement"
            f" matching the pattern {block_load_pattern}"
        )

    def test_has_a_valid_image(self, block: Type[Block]):
        logo_url = block._logo_url
        assert (
            logo_url is not None
        ), f"{block.__name__} is missing a value for _logo_url"
        img = Image.open(urlopen(logo_url))
        assert img.width == img.height, "Logo should be a square image"
        assert (
            1000 > img.width > 45
        ), f"Logo should be between 200px and 1000px wid, but is {img.width}px wide"
