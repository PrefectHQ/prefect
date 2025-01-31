import re
from abc import ABC, abstractmethod
from urllib.request import urlopen

import pytest
from PIL import Image

from prefect.blocks.core import Block


class BlockStandardTestSuite(ABC):
    @pytest.fixture
    @abstractmethod
    def block(self) -> type[Block]:
        pass

    def test_has_a_description(self, block: type[Block]) -> None:
        assert block.get_description()

    def test_has_a_documentation_url(self, block: type[Block]) -> None:
        assert block._documentation_url

    def test_all_fields_have_a_description(self, block: type[Block]) -> None:
        for name, field in block.model_fields.items():
            if Block.annotation_refers_to_block_class(field.annotation):
                # TODO: Block field descriptions aren't currently handled by the UI, so
                # block fields are currently excluded from this test. Once block field
                # descriptions are supported by the UI, remove this clause.
                continue
            assert field.description, (
                f"{block.__name__} is missing a description on {name}"
            )
            assert field.description.endswith("."), (
                f"{name} description on {block.__name__} does not end with a period"
            )

    def test_has_a_valid_code_example(self, block: type[Block]) -> None:
        code_example = block.get_code_example()
        assert code_example is not None, f"{block.__name__} is missing a code example"

        # Extract base name without generic parameters
        base_name = block.__name__.partition("[")[0]

        # Check for proper import statement
        import_pattern = rf"from .* import {base_name}"
        assert re.search(import_pattern, code_example) is not None, (
            f"The code example for {base_name} is missing an import statement"
            f" matching the pattern {import_pattern}"
        )

        # Check for proper load statement
        block_load_pattern = rf'.* = {base_name}\.load\("BLOCK_NAME"\)'
        assert re.search(block_load_pattern, code_example), (
            f"The code example for {base_name} is missing a .load statement"
            f" matching the pattern {block_load_pattern}"
        )

    def test_has_a_valid_image(self, block: type[Block]) -> None:
        logo_url = block._logo_url
        assert logo_url is not None, (
            f"{block.__name__} is missing a value for _logo_url"
        )
        img = Image.open(urlopen(str(logo_url)))
        assert img.width == img.height, "Logo should be a square image"
        assert 1000 > img.width > 45, (
            f"Logo should be between 200px and 1000px wid, but is {img.width}px wide"
        )
