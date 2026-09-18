import pickle
import random
from typing import Any

import httpx
import pytest
from pydantic import TypeAdapter

from prefect.utilities.annotations import allow_failure, freeze, unmapped
from prefect.utilities.callables import expand_mapping_parameters


class TestAllowFailure:
    @pytest.mark.parametrize(
        "annotation,expected_repr,include_blocked",
        [
            (allow_failure("value"), "allow_failure('value')", True),
            (
                allow_failure("value", include_blocked=False),
                "allow_failure('value', include_blocked=False)",
                False,
            ),
        ],
    )
    def test_preserves_one_element_tuple_interface(
        self,
        annotation: allow_failure[str],
        expected_repr: str,
        include_blocked: bool,
    ):
        assert isinstance(annotation, allow_failure)
        assert len(annotation) == 1
        assert tuple(annotation) == ("value",)
        assert annotation.unwrap() == "value"
        assert annotation.include_blocked is include_blocked
        assert repr(annotation) == expected_repr

    @pytest.mark.parametrize("include_blocked", [True, False])
    def test_is_picklable(self, include_blocked: bool):
        annotation = allow_failure("value", include_blocked=include_blocked)

        restored = pickle.loads(pickle.dumps(annotation))

        assert restored == annotation
        assert restored.include_blocked is include_blocked
        assert repr(restored) == repr(annotation)

    @pytest.mark.parametrize("include_blocked", [True, False])
    def test_rewrap_preserves_policy(self, include_blocked: bool):
        annotation = allow_failure("old", include_blocked=include_blocked)

        rewrapped = annotation.rewrap("new")

        assert rewrapped.unwrap() == "new"
        assert rewrapped.include_blocked is include_blocked

    def test_mapping_expansion_preserves_policy(self):
        def identity(value: str) -> str:
            return value

        parameters = expand_mapping_parameters(
            identity,
            {"value": allow_failure(["first", "second"], include_blocked=False)},
        )

        assert [parameter["value"].unwrap() for parameter in parameters] == [
            "first",
            "second",
        ]
        assert all(
            isinstance(parameter["value"], allow_failure)
            and not parameter["value"].include_blocked
            for parameter in parameters
        )

    def test_equality_is_preserved_for_each_policy(self):
        assert allow_failure("value") == allow_failure("value")
        assert allow_failure("value", include_blocked=False) == allow_failure(
            "value", include_blocked=False
        )


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

    @pytest.mark.parametrize(
        "value,expected_type",
        [
            ("test", str),
            (42, int),
            (3.14, float),
            (True, bool),
            (None, type(None)),
        ],
        ids=["str", "int", "float", "bool", "none"],
    )
    def test_frozen_parameters_are_serialized_as_json(
        self, value: Any, expected_type: type
    ):
        frozen = freeze(value)
        # assert it works even if we don't parameterize the expected type
        assert TypeAdapter(freeze).dump_python(frozen) == value
        # assert it works if we do parameterize the expected type
        assert TypeAdapter(freeze[expected_type]).dump_python(frozen) == value
