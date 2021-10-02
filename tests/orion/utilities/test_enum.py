import json
from prefect.orion.utilities.enum import AutoEnum


class Color(AutoEnum):
    RED = AutoEnum.auto()
    BLUE = AutoEnum.auto()


async def test_autoenum_generates_string_values():
    assert Color.RED.value == "RED"
    assert Color.BLUE.value == "BLUE"


async def test_autoenum_repr():
    assert repr(Color.RED) == str(Color.RED) == "Color.RED"


async def test_autoenum_can_be_json_serialized_with_default_encoder():
    json.dumps(Color.RED) == "RED"
