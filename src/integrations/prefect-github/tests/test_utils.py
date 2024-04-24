import json

import pytest
from prefect_github.utils import (
    camel_to_snake_case,
    initialize_return_fields_defaults,
    strip_kwargs,
)

test_config = {"categories": [{"category": ["title", "alias"]}, "total"]}


@pytest.mark.parametrize("string", ["someIDString", "SomeIDString", "some_id_string"])
def test_camel_to_snake_case(string):
    assert camel_to_snake_case(string) == "some_id_string"


def test_initialize_return_fields_defaults(tmp_path):
    config_path = tmp_path / "test_config.json"
    with open(config_path, "w") as f:
        json.dump(test_config, f)

    return_fields_defaults = initialize_return_fields_defaults(config_path)
    assert return_fields_defaults == {
        ("categories",): ["total"],
        ("categories", "category"): ["title", "alias"],
    }


def test_strip_kwargs():
    assert strip_kwargs(**{"a": None, "b": None}) == {}
    assert strip_kwargs(**{"a": "", "b": None}) == {"a": ""}
    assert strip_kwargs(**{"a": "abc", "b": "def"}) == {"a": "abc", "b": "def"}
    assert strip_kwargs(a="abc", b="def") == {"a": "abc", "b": "def"}
    assert strip_kwargs(**dict(a=[])) == {"a": []}
