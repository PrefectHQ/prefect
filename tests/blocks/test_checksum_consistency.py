"""
Tests that block schema checksums have remained stable between commits.

Once we have a versioning scheme in place for block schemas, this test can be removed.

Checksums have been generated using prefect release 2.0.2.
"""
import json
from pathlib import Path

import pytest

from prefect.blocks.core import Block
from prefect.utilities.dispatch import get_registry_for_type

with open(str(Path(__file__).parent) + "/checksums.json", "r") as f:
    standard_checksum = json.load(f)
block_registry = get_registry_for_type(Block) or {}


@pytest.mark.parametrize("block_key,block", block_registry.items())
def test_checksums_are_consistent(block_key, block):
    assert block._calculate_schema_checksum() == standard_checksum.get(
        block_key
    ), f"{block_key} checksum has changed or is not tracked in tests/blocks/checksums.json"
