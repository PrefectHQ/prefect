import random
from typing import Any

import httpx
import pytest

from prefect.utilities.annotations import freeze, unmapped


class TestUnmapped:
    def test_always_returns_same_value(self):
        thing = unmapped("hello")

        for _ in range(10):
            assert thing[random.randint(0, 100)] == "hello"


class TestFreeze:
    @pytest.mark.parametrize(
        "value",
        [
            "hello",
            42,
            3.14,
            True,
            None,
            ["a", 1, True],
            {"some", "set"},
            {
                "string": "value",
                "number": 42,
                "list": [1, "two", 3.0],
                "nested": {"a": [True, None]},
            },
        ],
        ids=["str", "int", "float", "bool", "none", "list", "set", "nested_dict"],
    )
    def test_round_trip(self, value: Any):
        assert freeze(value).unfreeze() == value

    @pytest.mark.parametrize(
        "value",
        [
            httpx.AsyncClient(),
            lambda: None,
            type("foo", (object,), {}),
        ],
        ids=["httpx_client", "lambda", "type"],
    )
    def test_non_json_serializable_raises(self, value: Any):
        """Test that freeze rejects non-JSON serializable types."""
        with pytest.raises(ValueError, match="Value must be JSON serializable"):
            freeze(value)
