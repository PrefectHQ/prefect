"""
Tests that block schema checksums have remained stable between commits.

Once we have a versioning scheme in place for block schemas, this test can be removed.

Checksums have been generated using prefect release 2.0.2.
"""

import json
from pathlib import Path

from prefect.blocks.core import Block
from prefect.utilities.dispatch import get_registry_for_type


def test_checksums_are_consistent():
    with open(str(Path(__file__).parent) + "/checksums.json", "r") as f:
        standard_checksum = json.load(f)

    for block_name, block in get_registry_for_type(Block).items():
        assert (
            block_name not in standard_checksum.keys()
            or block._calculate_schema_checksum() == standard_checksum[block_name]
        )
