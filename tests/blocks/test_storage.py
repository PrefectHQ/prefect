import pytest
from tempfile import TemporaryDirectory
from itertools import product
from prefect.blocks import storage

user_data = [
    # Test a couple forms of bytes
    b"test!",
    bytes([0, 1, 2]),
]

storage_blocks = [
    storage.OrionStorageBlock.parse_obj({"blockref": "orionstorage-block"}),
    storage.TempStorageBlock.parse_obj({"blockref": "tempstorage-block"}),
    storage.LocalStorageBlock.parse_obj(
        {"blockref": "localstorage-block", "storage_path": TemporaryDirectory().name}
    ),
]


@pytest.mark.parametrize(
    ["user_data", "storage_block"], product(user_data, storage_blocks)
)
async def test_write_and_read_rountdrips(
    user_data,
    storage_block,
):
    storage_token = await storage_block.write(user_data)
    assert await storage_block.read(storage_token) == user_data
